##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""
import logging
import os
import shutil
import zlib
from collections import defaultdict
from itertools import chain
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional, Union

from fab.artefacts import ArtefactsGetter, FilterBuildTrees
from fab.build_config import FlagsConfig
from fab.constants import OBJECT_FILES
from fab.dep_tree import AnalysedFile
from fab.metrics import send_metric
from fab.steps import check_for_errors, Step
from fab.tools import COMPILERS, remove_managed_flags, flags_checksum, run_command, get_tool, get_compiler_version
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, Timer, by_type, \
    file_checksum

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')


class CompileFortran(Step):
    """
    Compiles all Fortran files in all build trees, creating or extending a set of compiled files for each target.

    This step uses multiprocessing.
    The files are compiled in multiple passes, with each pass enabling further files to be compiled in the next pass.

    """
    def __init__(self, compiler: Optional[str] = None, common_flags: Optional[List[str]] = None,
                 path_flags: Optional[List] = None, source: Optional[ArtefactsGetter] = None,
                 two_stage_flag=None, name='compile fortran'):
        """
        :param compiler:
            The command line compiler to call. Defaults to `gfortran -c`.
        :param common_flags:
            A list of strings to be included in the command line call, for all files.
        :param path_flags:
            A list of :class:`~fab.build_config.AddFlags`, defining flags to be included in the command line call
            for selected files.
        :param source:
            An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.
        :param two_stage_flag:
            Optionally supply a flag which enables the 'syntax checking' feature of the compiler.
            Fab uses this to quickly build all the mod files first, potentially shortening dependency bottlenecks.
            The slower object file compilation can then follow in a second stage, all at once.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name=name)

        # Command line tools are sometimes specified with flags attached.
        self.compiler, compiler_flags = get_fortran_compiler(compiler)
        self.compiler_version = get_compiler_version(self.compiler)
        logger.info(f'fortran compiler is {self.compiler} {self.compiler_version}')

        # collate the flags
        env_flags = os.getenv('FFLAGS', '').split()
        common_flags = compiler_flags + env_flags + (common_flags or [])

        # Do we know this compiler? If so we can manage the flags a little, to avoid duplication or misconfiguration.
        # todo: This has been raised for discussion - we might never want to modify incoming flags...
        known_compiler = COMPILERS.get(self.compiler)
        if known_compiler:
            common_flags = remove_managed_flags(self.compiler, common_flags)
        else:
            logger.warning(f"Unknown compiler {self.compiler}. Fab cannot control certain flags."
                           "Please ensure you specify the flag `-c` equivalent flag to only compile."
                           "Please ensure the module output folder is set to your config's build_output folder."
                           "or please extend fab.tools.COMPILERS in your build script.")

        self.flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.two_stage_flag = two_stage_flag

        # runtime
        self._stage = None
        self._mod_hashes: Dict[str, int] = {}

    def run(self, artefact_store, config):
        """
        Compile all Fortran files in all build trees.

        Uses multiprocessing, unless disabled in the *config*.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)
        logger.info(f'fortran compiler is {self.compiler} {self.compiler_version}')

        # get all the source to compile, for all build trees, into one big lump
        build_lists: Dict[str, List] = self.source_getter(artefact_store)

        # compile everything in multiple passes
        compiled: Dict[Path, CompiledFile] = {}
        uncompiled: Set[AnalysedFile] = set(sum(build_lists.values(), []))
        logger.info(f"compiling {len(uncompiled)} fortran files")

        if self.two_stage_flag:
            logger.info("Starting two-stage compile: mod files, multiple passes")
            self._stage = 1

        while uncompiled:
            uncompiled = self.compile_pass(compiled, uncompiled, config)
        log_or_dot_finish(logger)

        if self.two_stage_flag:
            logger.info("Finalising two-stage compile: object files, single pass")
            self._stage = 2

            # a single pass should now compile all the object files in one go
            uncompiled = set(sum(build_lists.values(), []))  # todo: order by last compile duration
            results_this_pass = self.run_mp(items=uncompiled, func=self.process_file)
            log_or_dot_finish(logger)
            check_for_errors(results_this_pass, caller_label=self.name)
            compiled_this_pass = list(by_type(results_this_pass, CompiledFile))
            logger.info(f"stage 2 compiled {len(compiled_this_pass)} files")

        # record the compilation results for the next step
        self.store_artefacts(compiled, build_lists, artefact_store)

    def compile_pass(self, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFile], config):

        # what can we compile next?
        compile_next = self.get_compile_next(compiled, uncompiled)

        # compile
        logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
        results_this_pass = self.run_mp(items=compile_next, func=self.process_file)

        # there's a compilation result and a list of prebuild files for each compiled file
        compilation_results, prebuild_files = zip(*results_this_pass) if results_this_pass else (tuple(), tuple())
        check_for_errors(compilation_results, caller_label=self.name)
        compiled_this_pass = list(by_type(compilation_results, CompiledFile))
        logger.debug(f"compiled {len(compiled_this_pass)} files")

        # record the prebuild files as being current, so the cleanup knows not to delete them
        config.add_current_prebuilds(chain(*prebuild_files))

        # hash the modules we just created
        new_mod_hashes = get_mod_hashes(compile_next, config)
        self._mod_hashes.update(new_mod_hashes)

        # add compiled files to all compiled files
        compiled.update({cf.input_fpath: cf for cf in compiled_this_pass})

        # remove compiled files from remaining files
        uncompiled = set(filter(lambda af: af.fpath not in compiled, uncompiled))
        return uncompiled

    def get_compile_next(self, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFile]) -> Set[AnalysedFile]:

        # find what to compile next
        compile_next = set()
        not_ready: Dict[Path, List[Path]] = {}
        for af in uncompiled:
            # all deps ready?
            unfulfilled = [dep for dep in af.file_deps if dep not in compiled and dep.suffix == '.f90']
            if unfulfilled:
                not_ready[af.fpath] = unfulfilled
            else:
                compile_next.add(af)

        # unable to compile anything?
        if len(uncompiled) and not compile_next:
            msg = 'Nothing more can be compiled due to unfulfilled dependencies:\n'
            for f, unf in not_ready.items():
                msg += f'\n\n{f}'
                for u in unf:
                    msg += f'\n    {str(u)}'

            raise ValueError(msg)

        return compile_next

    def store_artefacts(self, compiled_files: Dict[Path, CompiledFile], build_lists: Dict[str, List], artefact_store):
        """
        Create our artefact collection; object files for each compiled file, per root symbol.

        """
        # add the new object files to the artefact store, by target
        lookup = {c.input_fpath: c for c in compiled_files.values()}
        object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
        for root, source_files in build_lists.items():
            new_objects = [lookup[af.fpath].output_fpath for af in source_files]
            object_files[root].update(new_objects)

    def process_file(self, analysed_file: AnalysedFile) \
            -> Union[Tuple[CompiledFile, List[Path]], Tuple[Exception, None]]:
        """
        Prepare to compile a fortran file, and compile it if anything has changed since it was last compiled.

        Object files are created directly as artefacts in the prebuild folder.
        Mod files are created in the module folder and copied as artefacts into the prebuild folder.
        If nothing has changed, prebuilt mod files are copied *from* the prebuild folder into the module folder.

        .. note::

            Prebuild filenames include a "combo-hash" of everything that, if changed, must trigger a recompile.
            For mod and object files, this includes a checksum of: *source code, compiler*.
            For object files, this also includes a checksum of: *compiler flags, modules on which we depend*.

            Before compiling a file, we calculate the combo hashes and see if the output files already exists.

        Returns a compilation result, regardless of whether it was compiled or prebuilt.

        """
        flags = self.flags.flags_for_path(path=analysed_file.fpath, config=self._config)
        mod_combo_hash = self._get_mod_combo_hash(analysed_file)
        obj_combo_hash = self._get_obj_combo_hash(analysed_file, flags)

        # calculate the incremental/prebuild artefact filenames
        obj_file_prebuild = self._config.prebuild_folder / f'{analysed_file.fpath.stem}.{obj_combo_hash:x}.o'
        mod_file_prebuilds = [
            self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod'
            for mod_def in analysed_file.module_defs
        ]

        # have we got all the prebuilt artefacts we need to avoid a recompile?
        prebuilds_exist = list(map(lambda f: f.exists(), [obj_file_prebuild] + mod_file_prebuilds))
        if not all(prebuilds_exist):
            # compile
            try:
                logger.debug(f'CompileFortran compiling {analysed_file.fpath}')
                self.compile_file(analysed_file, flags, output_fpath=obj_file_prebuild)
            except Exception as err:
                return Exception(f"Error compiling {analysed_file.fpath}:\n{err}"), None

            # copy the mod files to the prebuild folder as artefacts for reuse
            # note: perhaps we could sometimes avoid these copies because mods can change less frequently than obj
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    self._config.build_output / f'{mod_def}.mod',
                    self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                )

        else:
            log_or_dot(logger, f'CompileFortran using prebuild: {analysed_file.fpath}')

            # copy the prebuilt mod files from the prebuild folder
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                    self._config.build_output / f'{mod_def}.mod',
                )

        # return the results
        compiled_file = CompiledFile(input_fpath=analysed_file.fpath, output_fpath=obj_file_prebuild)
        artefacts = [obj_file_prebuild] + mod_file_prebuilds

        return compiled_file, artefacts

    def _get_obj_combo_hash(self, analysed_file, flags):
        # get a combo hash of things which matter to the object file we define
        mod_deps_hashes = {mod_dep: self._mod_hashes.get(mod_dep, 0) for mod_dep in analysed_file.module_deps}
        try:
            obj_combo_hash = sum([
                analysed_file.file_hash,
                flags_checksum(flags),
                sum(mod_deps_hashes.values()),
                zlib.crc32(self.compiler.encode()),
                zlib.crc32(self.compiler_version.encode()),
            ])
        except TypeError:
            raise ValueError("could not generate combo hash for object file")
        return obj_combo_hash

    def _get_mod_combo_hash(self, analysed_file):
        # get a combo hash of things which matter to the mod files we define
        try:
            mod_combo_hash = sum([
                analysed_file.file_hash,
                zlib.crc32(self.compiler.encode()),
                zlib.crc32(self.compiler_version.encode()),
            ])
        except TypeError:
            raise ValueError("could not generate combo hash for mod files")
        return mod_combo_hash

    def compile_file(self, analysed_file, flags, output_fpath):
        """
        Call the compiler.

        The current working folder for the command is set to the folder where the source file lives.
        This is done to stop the compiler inserting folder information into the mod files,
        which would cause them to have different checksums depending on where they live.

        """
        with Timer() as timer:
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

            # tool
            command = [self.compiler]
            known_compiler = COMPILERS.get(self.compiler)

            # Compile flag.
            # If it's an unknown compiler, we rely on the user config to specify this.
            if known_compiler:
                command.append(known_compiler.compile_flag)

            # flags
            command.extend(flags)
            if self.two_stage_flag and self._stage == 1:
                command.append(self.two_stage_flag)

            # Module folder.
            # If it's an unknown compiler, we rely on the user config to specify this.
            if known_compiler:
                command.extend([known_compiler.module_folder_flag, str(self._config.build_output)])

            # files
            command.append(analysed_file.fpath.name)
            command.extend(['-o', str(output_fpath)])

            log_or_dot(logger, 'CompileFortran running command: ' + ' '.join(command))

            run_command(command, cwd=analysed_file.fpath.parent)

        # todo: probably better to record both mod and obj metrics
        metric_name = self.name + (f' stage {self._stage}' if self._stage else '')
        send_metric(
            group=metric_name,
            name=str(analysed_file.fpath),
            value={'time_taken': timer.taken, 'start': timer.start})


def get_fortran_compiler(compiler: Optional[str] = None):
    """
    Get the fortran compiler specified by the `$FC` environment variable,
    or overridden by the optional `compiler` argument.

    Separates the tool and flags for the sort of value we see in environment variables, e.g. `gfortran -c`.

    :param compiler:
        Use this string instead of the $FC environment variable.

    """
    return get_tool(compiler or os.getenv('FC', ''))  # type: ignore


def get_mod_hashes(analysed_files: Set[AnalysedFile], config) -> Dict[str, int]:
    """
    Get the hash of every module file defined in the list of analysed files.

    """
    mod_hashes = {}
    for af in analysed_files:
        for mod_def in af.module_defs:
            fpath: Path = config.build_output / f'{mod_def}.mod'
            mod_hashes[mod_def] = file_checksum(fpath).file_hash

    return mod_hashes

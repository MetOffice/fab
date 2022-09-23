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
from pathlib import Path
from typing import List, Set, Dict

from fab.constants import OBJECT_FILES

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, run_command, Timer, by_type, \
    get_mod_hashes, string_checksum, flags_checksum, remove_minus_J
from fab.steps import check_for_errors
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')


class CompileFortran(MpExeStep):
    """
    Compiles all Fortran files in all build trees, creating or extending a set of compiled files for each target.

    This step uses multiprocessing.
    The files are compiled in multiple passes, with each pass enabling further files to be compiled in the next pass.

    """
    def __init__(self, compiler: str = None, common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, two_stage_flag=None, name='compile fortran'):
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

        # todo: Fab should be compiler-aware
        compiler = compiler or os.getenv('FC', 'gfortran -c')
        common_flags = common_flags or []
        env_flags = os.getenv('FFLAGS', '').split()
        super().__init__(
            exe=compiler,
            common_flags=remove_minus_J(common_flags + env_flags, verbose=True),
            path_flags=path_flags,
            name=name,
        )
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

        self.store_artefacts(compiled, build_lists, artefact_store)

    def compile_pass(self, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFile], config):

        # what can we compile next?
        compile_next = self.get_compile_next(compiled, uncompiled)

        # compile
        logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
        results_this_pass = self.run_mp(items=compile_next, func=self.process_file)
        check_for_errors(results_this_pass, caller_label=self.name)
        compiled_this_pass = list(by_type(results_this_pass, CompiledFile))
        logger.debug(f"compiled {len(compiled_this_pass)} files")

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

    def store_artefacts(self, compiled_files: Dict[Path, CompiledFile], build_trees: Dict[str, List], artefact_store):
        """
        Create our artefact collection; object files for each compiled file, per root symbol.

        """
        # add the targets' new object files to the artefact store
        lookup = {compiled_file.input_fpath: compiled_file for compiled_file in compiled_files.values()}
        object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
        for root, source_files in build_trees.items():
            new_objects = [lookup[af.fpath].output_fpath for af in source_files]
            object_files[root].update(new_objects)

    def process_file(self, analysed_file: AnalysedFile):
        # todo: include compiler version in hashes

        # get a combo hash of things which matter to the mod files we define
        mod_combo_hash = sum([analysed_file.file_hash, zlib.crc32(self.exe.encode())])
        mod_file_prebuilds = {self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod'
                              for mod_def in analysed_file.module_defs}

        # get a combo hash of things which matter to the object file we define
        flags = self.flags.flags_for_path(path=analysed_file.fpath, config=self._config)
        mod_deps_hashes = {mod_dep: self._mod_hashes[mod_dep] for mod_dep in analysed_file.module_deps}
        obj_combo_hash = sum([analysed_file.file_hash, flags_checksum(flags),
            sum(mod_deps_hashes.values()), zlib.crc32(self.exe.encode())])
        obj_file_prebuild = self._config.prebuild_folder / f'{analysed_file.fpath.stem}.{obj_combo_hash:x}.o'

        # have we got the object and all the mod files we need to avoid a recompile?
        prebuilds = [obj_file_prebuild, *mod_file_prebuilds]
        prebuilds_exist = list(map(lambda f: f.exists(), prebuilds))
        if not all(prebuilds_exist):

            # compile
            try:
                logger.debug(f'CompileFortran compiling {analysed_file.fpath}')
                self.compile_file(analysed_file, flags, output_fpath=obj_file_prebuild)
            except Exception as err:
                return Exception(f"Error compiling {analysed_file.fpath}: {err}")

            # Store the mod files for reuse.
            # todo: we could sometimes avoid these copies if we've got a prebuild
            #       from different flags (which don't affect mods).
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    self._config.build_output / f'{mod_def}.mod',
                    self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                )

        else:
            # restore the mod files we would have created
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    self._config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                    self._config.build_output / f'{mod_def}.mod',
                )

            log_or_dot(logger, f'CompileFortran skipping: {analysed_file.fpath}')

        return CompiledFile(input_fpath=analysed_file.fpath, output_fpath=obj_file_prebuild)

    def compile_file(self, analysed_file, flags, output_fpath):
        with Timer() as timer:
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

            # tool
            command = self.exe.split()

            # flags
            command.extend(flags)
            if self.two_stage_flag and self._stage == 1:
                command.append(self.two_stage_flag)
            # todo: Fab should be compiler aware. Some compilers might not use -J for this.
            command.extend(['-J', str(self._config.build_output)])

            # files
            command.append(str(analysed_file.fpath))
            command.extend(['-o', str(output_fpath)])

            log_or_dot(logger, 'CompileFortran running command: ' + ' '.join(command))
            run_command(command)

        # todo: probably better to record both mod and obj metrics
        metric_name = self.name + (f' stage {self._stage}' if self._stage else '')
        send_metric(
            group=metric_name,
            name=str(analysed_file.fpath),
            value={'time_taken': timer.taken, 'start': timer.start})

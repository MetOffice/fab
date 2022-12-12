##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
C file compilation.

"""
import logging
import os
import warnings
import zlib
from collections import defaultdict
from typing import List, Dict, Optional

from fab.artefacts import ArtefactsGetter, FilterBuildTrees
from fab.build_config import FlagsConfig
from fab.constants import OBJECT_FILES
from fab.dep_tree import AnalysedFile
from fab.metrics import send_metric
from fab.steps import check_for_errors, Step
from fab.tasks import TaskException
from fab.util import CompiledFile, log_or_dot, Timer, by_type
from fab.tools import flags_checksum, run_command, get_tool, get_compiler_version

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.c')
DEFAULT_OUTPUT_ARTEFACT = ''


class CompileC(Step):
    """
    Compiles all C files in all build trees, creating or extending a set of compiled files for each target.

    This step uses multiprocessing.
    All C files are compiled in a single pass.

    """
    # todo: tell the compiler (and other steps) which artefact name to create?
    def __init__(self, compiler: Optional[str] = None, common_flags: Optional[List[str]] = None,
                 path_flags: Optional[List] = None, source: Optional[ArtefactsGetter] = None, name="compile c"):
        """
        :param compiler:
            The command line compiler to call. Defaults to `gcc -c`.
        :param common_flags:
            A list of strings to be included in the command line call, for all files.
        :param path_flags:
            A list of :class:`~fab.build_config.AddFlags`, defining flags to be included in the command line call
            for selected files.
        :param source:
            An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name=name)

        self.compiler, compiler_flags = get_tool(compiler or os.getenv('CC', 'gcc -c'))  # type: ignore
        self.compiler_version = get_compiler_version(self.compiler)
        logger.info(f'c compiler is {self.compiler} {self.compiler_version}')

        env_flags = os.getenv('CFLAGS', '').split()
        common_flags = compiler_flags + env_flags + (common_flags or [])

        # make sure we have a -c
        # todo: c compiler awareness, like we have with fortran?
        if '-c' not in common_flags:
            warnings.warn("Adding '-c' to C compiler flags")
            common_flags = ['-c'] + common_flags

        self.flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def run(self, artefact_store, config):
        """
        Uses multiprocessing, unless disabled in the *config*.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        # gather all the source to compile, for all build trees, into one big lump
        build_lists: Dict = self.source_getter(artefact_store)
        to_compile = sum(build_lists.values(), [])
        logger.info(f"compiling {len(to_compile)} c files")

        # compile everything in one go
        compilation_results = self.run_mp(items=to_compile, func=self._compile_file)
        check_for_errors(compilation_results, caller_label=self.name)
        compiled_c = list(by_type(compilation_results, CompiledFile))
        logger.info(f"compiled {len(compiled_c)} c files")

        # record the prebuild files as being current, so the cleanup knows not to delete them
        prebuild_files = {r.output_fpath for r in compiled_c}
        config.add_current_prebuilds(prebuild_files)

        # record the compilation results for the next step
        self.store_artefacts(compiled_c, build_lists, artefact_store)

    # todo: very similar code in fortran compiler
    def store_artefacts(self, compiled_files: List[CompiledFile], build_lists: Dict[str, List], artefact_store):
        """
        Create our artefact collection; object files for each compiled file, per root symbol.

        """
        # add the new object files to the artefact store, by target
        lookup = {c.input_fpath: c for c in compiled_files}
        object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
        for root, source_files in build_lists.items():
            new_objects = [lookup[af.fpath].output_fpath for af in source_files]
            object_files[root].update(new_objects)

    def _compile_file(self, analysed_file: AnalysedFile):

        flags = self.flags.flags_for_path(path=analysed_file.fpath, config=self._config)
        obj_combo_hash = self._get_obj_combo_hash(analysed_file, flags)

        obj_file_prebuild = self._config.prebuild_folder / f'{analysed_file.fpath.stem}.{obj_combo_hash:x}.o'

        # prebuild available?
        if obj_file_prebuild.exists():
            log_or_dot(logger, f'CompileC using prebuild: {analysed_file.fpath}')
        else:
            with Timer() as timer:
                obj_file_prebuild.parent.mkdir(parents=True, exist_ok=True)

                command = self.compiler.split()  # type: ignore
                command.extend(flags)
                command.append(str(analysed_file.fpath))
                command.extend(['-o', str(obj_file_prebuild)])

                log_or_dot(logger, 'CompileC running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    return TaskException(f"error compiling {analysed_file.fpath}:\n{err}")

            send_metric(self.name, str(analysed_file.fpath), timer.taken)

        return CompiledFile(input_fpath=analysed_file.fpath, output_fpath=obj_file_prebuild)

    def _get_obj_combo_hash(self, analysed_file, flags):
        # get a combo hash of things which matter to the object file we define
        try:
            obj_combo_hash = sum([
                analysed_file.file_hash,
                flags_checksum(flags),
                zlib.crc32(self.compiler.encode()),
                zlib.crc32(self.compiler_version.encode()),
            ])
        except TypeError:
            raise ValueError("could not generate combo hash for object file")
        return obj_combo_hash

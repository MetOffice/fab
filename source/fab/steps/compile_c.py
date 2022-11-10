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
from collections import defaultdict
from typing import List, Dict, Optional

from fab.build_config import FlagsConfig
from fab.constants import OBJECT_FILES

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.tasks import TaskException
from fab.util import CompiledFile, run_command, log_or_dot, Timer, by_type
from fab.steps import check_for_errors, Step
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

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

        self.compiler = compiler or os.getenv('CC', 'gcc -c')
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
        results = self.run_mp(items=to_compile, func=self._compile_file)
        check_for_errors(results, caller_label=self.name)
        compiled_c = by_type(results, CompiledFile)

        lookup = {compiled_file.input_fpath: compiled_file for compiled_file in compiled_c}
        logger.info(f"compiled {len(lookup)} c files")

        # add the targets' new object files to the artefact store
        target_object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
        for root, source_files in build_lists.items():
            new_objects = [lookup[af.fpath].output_fpath for af in source_files]
            target_object_files[root].update(new_objects)

    # todo: identical to the fortran version - make a super class
    def _compile_file(self, analysed_file: AnalysedFile):
        # todo: should really use input_to_output_fpath() here
        output_fpath = analysed_file.fpath.with_suffix('.o')

        # already compiled?
        if self._config.reuse_artefacts and output_fpath.exists():
            log_or_dot(logger, f'CompileC skipping: {analysed_file.fpath}')
        else:
            with Timer() as timer:
                output_fpath.parent.mkdir(parents=True, exist_ok=True)

                command = self.compiler.split()  # type: ignore
                command.extend(self.flags.flags_for_path(path=analysed_file.fpath, config=self._config))
                command.append(str(analysed_file.fpath))
                command.extend(['-o', str(output_fpath)])

                log_or_dot(logger, 'CompileC running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    return TaskException(f"error compiling {analysed_file.fpath}:\n{err}")

            send_metric(self.name, str(analysed_file.fpath), timer.taken)

        return CompiledFile(analysed_file.fpath, output_fpath)

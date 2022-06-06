##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
C file compilation.

"""
import logging
import operator
import os
from collections import defaultdict
from typing import List

from fab.metrics import send_metric

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.tasks import TaskException
from fab.util import check_for_errors, CompiledFile, run_command, log_or_dot, Timer, by_type
from fab.artefacts import ArtefactsGetter, FilterBuildTrees

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.c')


class CompileC(MpExeStep):

    # todo: tell the compiler (and other steps) which artefact name to create?
    def __init__(self, compiler: str = None, common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, name="compile c"):
        compiler = compiler or os.getenv('CC', 'gcc -c')
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def run(self, artefact_store, config):
        """
        Compiles all C files in the *build_tree* artefact, creating the *compiled_c* artefact.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        # get all the source to compile, for all build targets, into one big lump
        target_source_lists = self.source_getter(artefact_store)
        big_lump = sum(target_source_lists, [])
        logger.info(f"compiling {len(big_lump)} c files")

        # compile
        results = self.run_mp(items=big_lump, func=self._compile_file)
        check_for_errors(results, caller_label=self.name)
        compiled_c = by_type(results, CompiledFile)
        logger.info(f"compiled {len(compiled_c)} c files")

        # collect the compiled files for each build target
        target_object_lists = {}
        lookup = {cf.analysed_file: cf for cf in compiled_c}
        for root, target_source_list in target_source_lists.items():
            target_object_lists[root] = [lookup[af] for af in target_source_list]

        # add the object lists to the artefact store
        artefact_collection = artefact_store.setdefault('target_object_lists', defaultdict(list))
        for root, target_object_list in target_object_lists.items():
            artefact_collection[root].append(target_object_list)

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

                command = self.exe.split()
                command.extend(self.flags.flags_for_path(
                    path=analysed_file.fpath,
                    source_root=self._config.source_root,
                    project_workspace=self._config.project_workspace))
                command.append(str(analysed_file.fpath))
                command.extend(['-o', str(output_fpath)])

                log_or_dot(logger, 'CompileC running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    return TaskException(f"error compiling {analysed_file.fpath}: {err}")

            send_metric(self.name, str(analysed_file.fpath), timer.taken)

        return CompiledFile(analysed_file, output_fpath)

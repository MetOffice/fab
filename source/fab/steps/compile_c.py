##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
C file compilation.

"""
import logging
from typing import List

from fab.dep_tree import AnalysedFile
from fab.steps.mp_exe import MpExeStep
from fab.tasks import TaskException
from fab.util import CompiledFile, run_command
from fab.artefacts import ArtefactsGetter, FilterBuildTree

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTree(suffix='.c')


class CompileC(MpExeStep):

    # todo: tell the compiler (and other steps) which artefact name to create?
    def __init__(self, compiler: str = 'gcc', common_flags: List[str] = None, path_flags: List = None,
                 source: ArtefactsGetter = None, name="compile c"):
        super().__init__(exe=compiler, common_flags=common_flags, path_flags=path_flags, name=name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER

    def run(self, artefact_store, config):
        """
        Compiles all C files in the *build_tree* artefact, creating the *compiled_c* artefact.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        to_compile = self.source_getter(artefact_store)
        logger.info(f"compiling {len(to_compile)} c files")

        # run
        results = self.run_mp(items=to_compile, func=self._compile_file)

        # any errors?
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            err_msg = '\n\n'.join(map(str, errors))
            raise RuntimeError(f"There were {len(errors)} errors compiling {len(to_compile)} c files:\n{err_msg}")

        # results
        compiled_c = [result for result in results if isinstance(result, CompiledFile)]
        logger.info(f"compiled {len(compiled_c)} c files")

        artefact_store['compiled_c'] = compiled_c

    def _compile_file(self, analysed_file: AnalysedFile):
        command = [self.exe]
        command.extend(self.flags.flags_for_path(
            path=analysed_file.fpath, source_root=self._config.source_root, workspace=self._config.project_workspace))
        command.append(str(analysed_file.fpath))

        output_file = analysed_file.fpath.with_suffix('.o')
        command.extend(['-o', str(output_file)])

        logger.debug('Running command: ' + ' '.join(command))

        try:
            run_command(command)
        except Exception as err:
            return TaskException(f"error compiling {analysed_file.fpath}: {err}")

        return CompiledFile(analysed_file, output_file)

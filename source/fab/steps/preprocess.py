"""
Fortran and C Preprocessing.

"""
import logging
from pathlib import PosixPath

from fab.config import FlagsConfig, AddPathFlags
from fab.dep_tree import by_type

from fab.steps import Step
from fab.tasks.c import _CTextReaderPragmas
from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, run_command

logger = logging.getLogger('fab')


class PreProcessor(Step):
    """
    Base class for preprocessors. A build step which calls a preprocessor.

    """
    def __init__(self, name='preprocess', preprocessor='cpp', common_flags=None, path_flags=None):
        """
        Args:
            - flags: Config object defining common and per-path flags.
            - workspace: The folder in which to find the source and output folders.

        Kwargs:
            - preprocessor: The name of the executable. Defaults to 'cpp'.
            - debug_skip: Ignore this for now!

        """
        super().__init__(name=name)

        self._preprocessor = preprocessor
        self._flags = FlagsConfig(
            common_flags=common_flags,
            all_path_flags=[AddPathFlags(path_filter=i[0], flags=i[1]) for i in path_flags]
        )

    def process_artefact(self, fpath):
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        output_fpath = input_to_output_fpath(workspace=self.workspace, input_path=fpath)

        # todo: split the language specific stuff out into the subclasses
        if fpath.suffix == ".c":
            # pragma injection
            # todo: The .prag file should probably live in the output folder.
            prag_output_fpath = fpath.parent / (fpath.name + ".prag")
            prag_output_fpath.open('w').writelines(_CTextReaderPragmas(fpath))
            input_fpath = prag_output_fpath
        elif fpath.suffix in [".f90", ".F90"]:
            input_fpath = fpath
            output_fpath = output_fpath.with_suffix('.f90')
        else:
            raise ValueError(f"Unexpected file type: '{str(fpath)}'")

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [self._preprocessor]
        command.extend(self._flags.flags_for_path(fpath))

        # input and output files
        command.append(str(input_fpath))
        command.append(str(output_fpath))

        log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error preprocessing {fpath}: {err}")

        return output_fpath


class FortranPreProcessor(PreProcessor):

    def __init__(self, name='fortran preprocess', preprocessor='cpp', common_flags=None, path_flags=None):
        super().__init__(name=name, preprocessor=preprocessor, common_flags=common_flags, path_flags=path_flags)

    def run(self, artefacts):
        """
        Preprocess all .F90 and .f90 files in the *all_source* artefact, creating the *preprocessed_fortran* artefact.

        """
        mp_input = artefacts['all_source']['.f90'] + artefacts['all_source']['.F90']

        results = self.run_mp(items=mp_input, func=self.process_artefact)

        # todo: move into run_mp?
        results_by_type = by_type(results)

        # any errors?
        if results_by_type[Exception]:
            formatted_errors = "\n\n".join(map(str, results_by_type[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(results_by_type[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)

        artefacts['preprocessed_fortran'] = results_by_type[PosixPath]


class CPreProcessor(PreProcessor):

    def __init__(self, name='c preprocess', preprocessor='cpp', common_flags=None, path_flags=None):
        super().__init__(name=name, preprocessor=preprocessor, common_flags=common_flags, path_flags=path_flags)

    def run(self, artefacts):
        """
        Preprocess all .c files in the *all_source* artefact, creating the *preprocessed_c* artefact.

        """

        mp_input = artefacts['all_source']['.c']

        results = self.run_mp(items=mp_input, func=self.process_artefact)

        # todo: move into run_mp?
        results_by_type = by_type(results)

        # any errors?
        if results_by_type[Exception]:
            formatted_errors = "\n\n".join(map(str, results_by_type[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(results_by_type[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)

        artefacts['preprocessed_c'] = results_by_type[PosixPath]

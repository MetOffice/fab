"""
Fortran and C Preprocessing.

"""
import logging
from pathlib import PosixPath, Path
from typing import List

from fab.config import FlagsConfig, AddPathFlags
from fab.dep_tree import by_type

from fab.steps import Step
from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, run_command, suffix_filter

logger = logging.getLogger('fab')


class PreProcessor(Step):
    """
    Base class for preprocessors. A build step which calls a preprocessor.

    """
    def __init__(self,
                 input_name, output_name, input_suffixes: List[str],
                 preprocessor='cpp', common_flags=None, path_flags=None, name='preprocess'):
        """
        Args:
            - flags: Config object defining common and per-path flags.
            - workspace: The folder in which to find the source and output folders.

        Kwargs:
            - preprocessor: The name of the executable. Defaults to 'cpp'.
            - debug_skip: Ignore this for now!

        """
        super().__init__(name=name)

        self.input_name = input_name
        self.output_name = output_name
        self.input_suffixes = input_suffixes

        self._preprocessor = preprocessor
        self._flags = FlagsConfig(
            common_flags=common_flags,
            all_path_flags=[AddPathFlags(path_filter=i[0], flags=i[1]) for i in path_flags]
        )

    def run(self, artefacts):
        """
        Preprocess all input files in the *all_source* artefact, creating the output artefact.

        Input files are defined by :attr:`~fab.steps.preprocess.PreProcessor.input_suffixes`
        and refer to entries in the *all_source* artefact.

        The output artefactis defined by :attr:`~fab.steps.preprocess.PreProcessor.output_artefact`.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        files = suffix_filter(artefacts[self.input_name], self.input_suffixes)
        results = self.run_mp(items=files, func=self.process_artefact)

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
        artefacts[self.output_name] = results_by_type[PosixPath]  # todo: why posix path?

    def output_path(self, input_path: Path):
        output_fpath = input_to_output_fpath(workspace=self.workspace, input_path=input_path)
        return output_fpath

    def process_artefact(self, fpath):
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        output_fpath = self.output_path(fpath)

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [self._preprocessor]
        command.extend(self._flags.flags_for_path(fpath))

        # input and output files
        command.append(str(fpath))
        command.append(str(output_fpath))

        log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
        try:
            run_command(command)
        except Exception as err:
            raise Exception(f"error preprocessing {fpath}: {err}")

        return output_fpath


class FortranPreProcessor(PreProcessor):
    """
    By default, preprocesses all .F90 and .f90 files in the *all_source* artefact, creating the *preprocessed_fortran* artefact.

    """
    def __init__(self, input_name='all_source', output_name='preprocessed_fortran',
                 preprocessor='cpp', common_flags=None, path_flags=None, name='fortran preprocess'):
        super().__init__(
            input_name, output_name, input_suffixes=['.f90', '.F90'],
            preprocessor=preprocessor, common_flags=common_flags, path_flags=path_flags, name=name)

    def output_path(self, input_path: Path):
        output_fpath = super().output_path(input_path)
        output_fpath = output_fpath.with_suffix(output_fpath.suffix.lower())
        return output_fpath


class CPreProcessor(PreProcessor):
    """
    By default, preprocesses all .c files in the *all_source* artefact, creating the *preprocessed_c* artefact.

    An example of setting *input_name* would be when preprocessing files which have come from the C pragma injector,
    which creates the *pragmad_c" artefact.

    """
    def __init__(self, input_name='all_source', output_name='preprocessed_c',
                 preprocessor='cpp', common_flags=None, path_flags=None, name='c preprocess',):
        super().__init__(
            input_name, output_name, input_suffixes=['.c'],
            preprocessor=preprocessor, common_flags=common_flags, path_flags=path_flags, name=name)

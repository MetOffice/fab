"""
Fortran and C Preprocessing.

"""
import logging
from pathlib import Path
from typing import List

from fab.dep_tree import by_type

from fab.steps.mp_exe import MpExeStep
from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, run_command, SourceGetter, FilterFpaths

logger = logging.getLogger('fab')


class PreProcessor(MpExeStep):
    """
    Base class for preprocessors. A build step which calls a preprocessor.

    """

    # todo: make abstract, we don't really need these in the base class
    DEFAULT_SOURCE = None
    DEFAULT_OUTPUT_NAME = ''
    DEFAULT_OUTPUT_SUFFIX = ''

    def __init__(self,
                 source: SourceGetter=None, output_artefact=None, output_suffix=None,
                 preprocessor='cpp', common_flags: List[str]=None, path_flags: List=None,
                 name='preprocess'):
        """
        Kwargs:
            - source: Defines the files to preprocess. Defaults to DEFAULT_SOURCE.
            - output_artefact: The name of the artefact, defaulting to DEFAULT_OUTPUT_NAME.
            - output_suffix: Defaults to DEFAULT_OUTPUT_SUFFIX.
            - preprocessor: The name of the executable. Defaults to 'cpp'.
            - common_flags: Used to construct a :class:`~fab.config.FlagsConfig' object.
            - path_flags: Used to construct a :class:`~fab.config.FlagsConfig' object.
            - name: Used for logger output.

        """
        super().__init__(exe=preprocessor, common_flags=common_flags, path_flags=path_flags, name=name)

        self.source_getter = source or self.DEFAULT_SOURCE
        self.output_artefact = output_artefact or self.DEFAULT_OUTPUT_NAME
        self.output_suffix = output_suffix or self.DEFAULT_OUTPUT_SUFFIX

    def run(self, artefacts, config):
        """
        Preprocess all input files from `self.source_getter`, creating `self.output_artefact`.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefacts, config)

        files = self.source_getter(artefacts)
        results = self.run_mp(items=files, func=self.process_artefact)
        # results_by_type = by_type(results)
        exceptions = by_type(results, Exception)

        # todo: this is not correct, as it won't pick up subtypes
        # any errors?
        if exceptions:
            formatted_errors = "\n\n".join(map(str, exceptions))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(exceptions)} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)
        artefacts[self.output_artefact] = by_type(results, Path)

    def process_artefact(self, fpath):
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        # output_fpath = self.output_path(fpath)
        output_fpath = input_to_output_fpath(workspace=self._config.workspace, input_path=fpath).with_suffix(self.output_suffix)

        # for dev speed, but this could become a good time saver with, e.g, hashes or something
        if self._config.debug_skip and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
            return output_fpath

        if not output_fpath.parent.exists():
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

        command = [self.exe]
        command.extend(self._flags.flags_for_path(fpath, self._config.workspace))

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
    By default, preprocesses all .F90 and .f90 files in the *all_source* artefact,
    creating the *preprocessed_fortran* artefact.

    """
    DEFAULT_SOURCE = FilterFpaths('all_source', ['.F90', '.f90'])
    DEFAULT_OUTPUT_NAME = 'preprocessed_fortran'
    DEFAULT_OUTPUT_SUFFIX = '.f90'


class CPreProcessor(PreProcessor):
    """
    By default, preprocesses all .c files in the *all_source* artefact, creating the *preprocessed_c* artefact.

    An example of providing a :class:`~fab.util.SourceGetter` would be
    when preprocessing files which have come from the C pragma injector,
    which creates the *pragmad_c" artefact.

    """
    DEFAULT_SOURCE = FilterFpaths('all_source', ['.c'])
    DEFAULT_OUTPUT_NAME = 'preprocessed_c'
    DEFAULT_OUTPUT_SUFFIX = '.c'

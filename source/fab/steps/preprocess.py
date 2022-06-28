##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran and C Preprocessing.

"""
import logging
import os
from pathlib import Path
from typing import List

from fab.metrics import send_metric

from fab.steps.mp_exe import MpExeStep
from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, run_command, Timer, by_type, check_for_errors
from fab.artefacts import ArtefactsGetter, SuffixFilter

logger = logging.getLogger(__name__)


class PreProcessor(MpExeStep):
    """
    Base class for preprocessors. A build step which calls a preprocessor.

    """
    DEFAULT_SOURCE: ArtefactsGetter
    DEFAULT_OUTPUT_NAME: str
    DEFAULT_OUTPUT_SUFFIX: str
    LABEL: str

    def __init__(self,
                 source: ArtefactsGetter = None, output_collection=None, output_suffix=None,
                 preprocessor='cpp', common_flags: List[str] = None, path_flags: List = None,
                 name=None):
        """
        Kwargs:
            - source: Defines the files to preprocess. Defaults to DEFAULT_SOURCE.
            - output_collection: The name of the output artefact collection, defaulting to DEFAULT_OUTPUT_NAME.
            - output_suffix: Defaults to DEFAULT_OUTPUT_SUFFIX.
            - preprocessor: The name of the executable. Defaults to 'cpp'.
            - common_flags: Used to construct a :class:`~fab.config.FlagsConfig' object.
            - path_flags: Used to construct a :class:`~fab.config.FlagsConfig' object.
            - name: Used for logger output.

        """
        super().__init__(exe=preprocessor, common_flags=common_flags, path_flags=path_flags, name=name or self.LABEL)

        self.source_getter = source or self.DEFAULT_SOURCE
        self.output_collection = output_collection or self.DEFAULT_OUTPUT_NAME
        self.output_suffix = output_suffix or self.DEFAULT_OUTPUT_SUFFIX

    def run(self, artefact_store, config):
        """
        Preprocess all input files from `self.source_getter`, creating the artefact collection named
        `self.output_collection`.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        files = list(self.source_getter(artefact_store))
        logger.info(f'preprocessing {len(files)} files')

        results = self.run_mp(items=files, func=self.process_artefact)
        check_for_errors(results, caller_label=self.name)

        log_or_dot_finish(logger)
        artefact_store[self.output_collection] = list(by_type(results, Path))

    def process_artefact(self, fpath):
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        output_fpath = input_to_output_fpath(
            source_root=self._config.source_root,
            project_workspace=self._config.project_workspace,
            input_path=fpath).with_suffix(self.output_suffix)

        # already preprocessed?
        if self._config.reuse_artefacts and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
        else:
            with Timer() as timer:
                output_fpath.parent.mkdir(parents=True, exist_ok=True)

                command = self.exe.split()
                command.extend(self.flags.flags_for_path(
                    path=fpath, source_root=self._config.source_root, project_workspace=self._config.project_workspace))
                command.append(str(fpath))
                command.append(str(output_fpath))

                log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    raise Exception(f"error preprocessing {fpath}: {err}")

            send_metric(self.name, str(fpath), timer.taken)

        return output_fpath


def fortran_preprocessor(preprocessor=None, source=None,
                         output_collection='preprocessed_fortran', output_suffix='.f90',
                         name='preprocess fortran', **pp_kwds):

    return PreProcessor(
        preprocessor=preprocessor or os.getenv('FPP', 'fpp -P'),
        source=source or SuffixFilter('all_source', '.F90'),
        output_collection=output_collection,
        output_suffix=output_suffix,
        name=name,
        **pp_kwds
    )


def c_preprocessor(preprocessor=None, source=None,
                   output_collection='preprocessed_c', output_suffix='.c',
                   name='preprocess c', **pp_kwds):

    return PreProcessor(
        preprocessor=preprocessor or os.getenv('CPP', 'cpp -P'),
        source=source or SuffixFilter('all_source', '.c'),
        output_collection=output_collection,
        output_suffix=output_suffix,
        name=name,
        **pp_kwds
    )

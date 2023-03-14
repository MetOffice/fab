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
from typing import Any, Dict, List, Optional

from fab.build_config import FlagsConfig
from fab.constants import PRAGMAD_C
from fab.metrics import send_metric

from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, Timer, by_type
from fab.tools import run_command
from fab.steps import check_for_errors, Step
from fab.artefacts import ArtefactsGetter, SuffixFilter, CollectionGetter
from fab.build_config import AddFlags


logger = logging.getLogger(__name__)


class PreProcessor(Step):
    """
    Preprocess Fortran or C files with multiprocessing.

    """
    DEFAULT_SOURCE: ArtefactsGetter
    DEFAULT_OUTPUT_NAME: str
    DEFAULT_OUTPUT_SUFFIX: str
    LABEL: str

    def __init__(self,
                 preprocessor: str,
                 source: Optional[ArtefactsGetter] = None,
                 output_collection: Optional[str] = None,
                 output_suffix: Optional[str] = None,
                 common_flags: Optional[List[str]] = None,
                 path_flags: Optional[List[AddFlags]] = None,
                 name: Optional[str] = None) -> None:
        """
        :param preprocessor:
            The preprocessor executable.
        :param source:
            Defines the files to preprocess. Defaults to DEFAULT_SOURCE.
        :param output_collection:
            The name of the output artefact collection, defaulting to DEFAULT_OUTPUT_NAME.
        :param output_suffix:
            Defaults to DEFAULT_OUTPUT_SUFFIX.
        :param common_flags:
            Used to construct a :class:`~fab.config.FlagsConfig` object.
        :param path_flags:
            Used to construct a :class:`~fab.build_config.FlagsConfig` object.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name=name or self.LABEL)

        # todo: should we manage known preprocessors like we do compilers, so we can ensure the -P flag is added?

        # Command line tools are sometimes specified with flags attached, e.g 'cpp -traditional-cpp'
        preprocessor_split = preprocessor.split()
        self.preprocessor = preprocessor_split[0]

        common_flags = preprocessor_split[1:] + (common_flags or [])
        self.flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

        self.source_getter = source or self.DEFAULT_SOURCE
        self.output_collection = output_collection or self.DEFAULT_OUTPUT_NAME
        self.output_suffix = output_suffix or self.DEFAULT_OUTPUT_SUFFIX

    def run(self, artefact_store: Dict[Any, Any], config: Any) -> None:
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
        logger.info(f'preprocessor for {self.name} is {self.preprocessor}')

        files = list(self.source_getter(artefact_store))
        logger.info(f'preprocessing {len(files)} files')

        results = self.run_mp(items=files, func=self._process_artefact)
        check_for_errors(results, caller_label=self.name)

        log_or_dot_finish(logger)
        artefact_store[self.output_collection] = list(by_type(results, Path))

    def _process_artefact(self, fpath: Path) -> Path:
        """
        Expects an input file in the source folder.
        Writes the output file to the output folder, with a lower case extension.

        """
        output_fpath = input_to_output_fpath(config=self._config, input_path=fpath).with_suffix(self.output_suffix)

        # already preprocessed?
        if self._config.reuse_artefacts and output_fpath.exists():  # type: ignore # confused by _config
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
        else:
            with Timer() as timer:
                output_fpath.parent.mkdir(parents=True, exist_ok=True)

                command = [self.preprocessor]
                command.extend(self.flags.flags_for_path(path=fpath, config=self._config))
                command.append(str(fpath))
                command.append(str(output_fpath))

                log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
                try:
                    run_command(command)
                except Exception as err:
                    raise Exception(f"error preprocessing {fpath}:\n{err}")

            send_metric(self.name, str(fpath), {'time_taken': timer.taken, 'start': timer.start})

        return output_fpath


def fortran_preprocessor(preprocessor: Optional[str] = None,
                         source: Optional[str] = None,
                         output_collection: str = 'preprxocessed_fortran',
                         output_suffix: str = '.f90',
                         name: str = 'preprocess fortran',
                         **pp_kwds: Any) -> PreProcessor:
    """
    Return a step to preprocess Fortran files with multiprocessing.

    Params as per :class:`~fab.steps.preprocess.PreProcessor`.

    """
    # todo: we want to add -P ... IF it's not already there
    return PreProcessor(
        preprocessor=preprocessor or os.getenv('FPP', 'fpp -P'),  # type: ignore # mypy is confused
        source=source or SuffixFilter('all_source', '.F90'),  # type: ignore # mypy is confused
        output_collection=output_collection,
        output_suffix=output_suffix,
        name=name,
        **pp_kwds
    )


class DefaultCPreprocessorSource(ArtefactsGetter):
    """
    A source getter specifically for c preprocessing.
    Looks for the default output from pragma injection, falls back to default source finder.
    This allows the step to work with or without a preceding pragma step.

    """
    def __call__(self, artefact_store: Dict[Any, Any]) -> Any:
        return CollectionGetter(PRAGMAD_C)(artefact_store) \
               or SuffixFilter('all_source', '.c')(artefact_store)


DEFAULT_C_SOURCE_GETTER = DefaultCPreprocessorSource()


def c_preprocessor(preprocessor: Optional[str] = None,
                   source: Optional[str] = None,
                   output_collection: str = 'preprocessed_c',
                   output_suffix: str = '.c',
                   name: str = 'preprocess c',
                   **pp_kwds: Any) -> PreProcessor:
    """
    Return a step to preprocess C files with multiprocessing.

    Params as per :class:`~fab.steps.preprocess.PreProcessor`.

    """
    return PreProcessor(
        preprocessor=preprocessor or os.getenv('CPP', 'cpp'),  # type: ignore # relates to previous todo?
        source=source or DEFAULT_C_SOURCE_GETTER,  # type: ignore # relates to previous todo?
        output_collection=output_collection,
        output_suffix=output_suffix,
        name=name,
        **pp_kwds
    )

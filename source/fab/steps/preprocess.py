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
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import PRAGMAD_C
from fab.metrics import send_metric

from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, Timer, by_type
from fab.tools import run_command
from fab.steps import check_for_errors, run_mp, Step, step_timer
from fab.artefacts import ArtefactsGetter, SuffixFilter, CollectionGetter

logger = logging.getLogger(__name__)


@dataclass
class MpCommonArgs(object):
    """Common args for calling process_artefact() using multiprocessing."""
    config: BuildConfig
    output_suffix: str
    preprocessor: str
    flags: FlagsConfig
    name: str


def pre_processor(config: BuildConfig, preprocessor: str,
                  source_getter: ArtefactsGetter, output_collection, output_suffix,
                  common_flags: List[str] = None,
                  path_flags: List = None,
                  name="preprocess"):
    """
    Preprocess Fortran or C files.

    Uses multiprocessing, unless disabled in the config.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param preprocessor:
        The preprocessor executable.
    :param source_getter:
        Defines the files to preprocess.
    :param output_collection:
        The name of the output artefact collection.
    :param output_suffix:
        Suffix for output files.
    :param common_flags:
        Used to construct a :class:`~fab.config.FlagsConfig` object.
    :param path_flags:
        Used to construct a :class:`~fab.build_config.FlagsConfig` object.
    :param name:
        Human friendly name for logger output, with sensible default.

    """
    # todo: should we manage known preprocessors like we do compilers, so we can ensure the -P flag is added?

    # Command line tools are sometimes specified with flags attached, e.g 'cpp -traditional-cpp'
    preprocessor_split = preprocessor.split()
    preprocessor = preprocessor_split[0]

    common_flags = preprocessor_split[1:] + (common_flags or [])
    flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

    logger.info(f'preprocessor is {preprocessor}')

    files = list(source_getter(config._artefact_store))
    logger.info(f'preprocessing {len(files)} files')

    # common args for the child process
    mp_common_args = MpCommonArgs(
        config=config,
        output_suffix=output_suffix,
        preprocessor=preprocessor,
        flags=flags,
        name=name,
    )

    # bundle files with common args
    mp_args = [(file, mp_common_args) for file in files]

    results = run_mp(config, items=mp_args, func=process_artefact)
    check_for_errors(results, caller_label=name)

    log_or_dot_finish(logger)
    config._artefact_store[output_collection] = list(by_type(results, Path))


def process_artefact(arg: Tuple[Path, MpCommonArgs]):
    """
    Expects an input file in the source folder.
    Writes the output file to the output folder, with a lower case extension.

    """
    fpath, args = arg

    # output_fpath = input_to_output_fpath(config=self._config, input_path=fpath).with_suffix(self.output_suffix)
    output_fpath = input_to_output_fpath(config=args.config, input_path=fpath).with_suffix(args.output_suffix)

    # already preprocessed?
    # todo: remove reuse_artefacts eveywhere!
    if args.config.reuse_artefacts and output_fpath.exists():
        log_or_dot(logger, f'Preprocessor skipping: {fpath}')
    else:
        with Timer() as timer:
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

            command = [args.preprocessor]
            command.extend(args.flags.flags_for_path(path=fpath, config=args.config))
            command.append(str(fpath))
            command.append(str(output_fpath))

            log_or_dot(logger, 'PreProcessor running command: ' + ' '.join(command))
            try:
                run_command(command)
            except Exception as err:
                raise Exception(f"error preprocessing {fpath}:\n{err}")

        send_metric(args.name, str(fpath), {'time_taken': timer.taken, 'start': timer.start})

    return output_fpath


# todo: rename preprocess_fortran
@step_timer
def preprocess_fortran(config: BuildConfig, source=None, **kwargs):
    """
    Wrapper to pre_processor for Fortran files.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.

    The preprocessor is taken from the `FPP` environment, or falls back to `fpp -P`.

    If source is not provided, it defaults to `SuffixFilter('all_source', '.F90')`.

    """
    return pre_processor(
        config,
        preprocessor=os.getenv('FPP', 'fpp -P'),  # todo: call get_fortran_preprocessor() instead
        source_getter=source or SuffixFilter('all_source', '.F90'),
        output_collection='preprocessed_fortran', output_suffix='.f90',
        **kwargs,
    )


class DefaultCPreprocessorSource(ArtefactsGetter):
    """
    A source getter specifically for c preprocessing.
    Looks for the default output from pragma injection, falls back to default source finder.
    This allows the step to work with or without a preceding pragma step.

    """
    def __call__(self, artefact_store):
        return CollectionGetter(PRAGMAD_C)(artefact_store) \
               or SuffixFilter('all_source', '.c')(artefact_store)

# todo: rename preprocess_c
@step_timer
def preprocess_c(config: BuildConfig, source=None, **kwargs):
    """
    Wrapper to pre_processor for C files.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.

    The preprocessor is taken from the `CPP` environment, or falls back to `cpp`.

    If source is not provided, it defaults to :class:`~fab.steps.preprocess.DefaultCPreprocessorSource`.

    """
    return pre_processor(
        config,
        preprocessor=os.getenv('CPP', 'cpp'),
        source_getter=source or DefaultCPreprocessorSource(),
        output_collection='preprocessed_c', output_suffix='.c',
        **kwargs,
    )

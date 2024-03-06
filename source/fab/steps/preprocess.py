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
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Tuple

from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import PRAGMAD_C
from fab.metrics import send_metric

from fab.util import log_or_dot_finish, input_to_output_fpath, log_or_dot, suffix_filter, Timer, by_type
from fab.tools import get_tool, run_command
from fab.steps import check_for_errors, run_mp, step
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
                  files: Collection[Path], output_collection, output_suffix,
                  common_flags: Optional[List[str]] = None,
                  path_flags: Optional[List] = None,
                  name="preprocess"):
    """
    Preprocess Fortran or C files.

    Uses multiprocessing, unless disabled in the config.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param preprocessor:
        The preprocessor executable.
    :param files:
        The files to preprocess.
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
    common_flags = common_flags or []
    flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

    logger.info(f'preprocessor is {preprocessor}')

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
    config.artefact_store[output_collection] = list(by_type(results, Path))


def process_artefact(arg: Tuple[Path, MpCommonArgs]):
    """
    Expects an input file in the source folder.
    Writes the output file to the output folder, with a lower case extension.

    """
    fpath, args = arg

    with Timer() as timer:

        # output_fpath = input_to_output_fpath(config=self._config, input_path=fpath).with_suffix(self.output_suffix)
        output_fpath = input_to_output_fpath(config=args.config, input_path=fpath).with_suffix(args.output_suffix)

        # already preprocessed?
        # todo: remove reuse_artefacts eveywhere!
        if args.config.reuse_artefacts and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {fpath}')
        else:
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


def get_fortran_preprocessor():
    """
    Identify the fortran preprocessor and any flags from the environment.

    Initially looks for the `FPP` environment variable, then tries to call the `fpp` and `cpp` command line tools.

    Returns the executable and flags.

    The returned flags will always include `-P` to suppress line numbers.
    This fparser ticket requests line number handling https://github.com/stfc/fparser/issues/390 .

    """
    fpp: Optional[str] = None
    fpp_flags: Optional[List[str]] = None

    try:
        fpp, fpp_flags = get_tool(os.getenv('FPP'))
        logger.info(f"The environment defined FPP as '{fpp}'")
    except ValueError:
        pass

    if not fpp:
        try:
            run_command(['which', 'fpp'])
            fpp, fpp_flags = 'fpp', ['-P']
            logger.info('detected fpp')
        except RuntimeError:
            # fpp not available
            pass

    if not fpp:
        try:
            run_command(['which', 'cpp'])
            fpp, fpp_flags = 'cpp', ['-traditional-cpp', '-P']
            logger.info('detected cpp')
        except RuntimeError:
            # fpp not available
            pass

    if not fpp:
        raise RuntimeError('no fortran preprocessor specified or discovered')

    assert fpp_flags is not None
    if '-P' not in fpp_flags:
        fpp_flags.append('-P')

    return fpp, fpp_flags


# todo: rename preprocess_fortran
@step
def preprocess_fortran(config: BuildConfig, source: Optional[ArtefactsGetter] = None, **kwargs):
    """
    Wrapper to pre_processor for Fortran files.

    Ensures all preprocessed files are in the build output.
    This means *copying* already preprocessed files from source to build output.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.

    The preprocessor is taken from the `FPP` environment, or falls back to `fpp -P`.

    If source is not provided, it defaults to `SuffixFilter('all_source', '.F90')`.

    """
    source_getter = source or SuffixFilter('all_source', ['.F90', '.f90'])
    source_files = source_getter(config.artefact_store)
    F90s = suffix_filter(source_files, '.F90')
    f90s = suffix_filter(source_files, '.f90')

    # get the tool from FPP
    fpp, fpp_flags = get_fortran_preprocessor()

    # make sure any flags from FPP are included in any common flags specified by the config
    try:
        common_flags = kwargs.pop('common_flags')
    except KeyError:
        common_flags = []
    for fpp_flag in fpp_flags:
        if fpp_flag not in common_flags:
            common_flags.append(fpp_flag)

    # preprocess big F90s
    pre_processor(
        config,
        preprocessor=fpp,
        common_flags=common_flags,
        files=F90s,
        output_collection='preprocessed_fortran', output_suffix='.f90',
        name='preprocess fortran',
        **kwargs,
    )

    all_preprocessed_files = config.artefact_store["preprocessed_fortran"]
    config.artefact_store.add_fortran_build_files(all_preprocessed_files)

    # todo: parallel copy?
    # copy little f90s from source to output folder
    logger.info(f'Fortran preprocessor copying {len(f90s)} files to build_output')
    for f90 in f90s:
        output_path = input_to_output_fpath(config, input_path=f90)
        if output_path != f90:
            if not output_path.parent.exists():
                output_path.parent.mkdir(parents=True)
            log_or_dot(logger, f'copying {f90}')
            shutil.copyfile(str(f90), str(output_path))
            config.artefact_store.add_fortran_build_files(output_path)


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
@step
def preprocess_c(config: BuildConfig, source=None, **kwargs):
    """
    Wrapper to pre_processor for C files.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.

    The preprocessor is taken from the `CPP` environment, or falls back to `cpp`.

    If source is not provided, it defaults to :class:`~fab.steps.preprocess.DefaultCPreprocessorSource`.

    """
    source_getter = source or DefaultCPreprocessorSource()
    source_files = source_getter(config.artefact_store)

    pre_processor(
        config,
        preprocessor=os.getenv('CPP', 'cpp'),
        files=source_files,
        output_collection='preprocessed_c', output_suffix='.c',
        name='preprocess c',
        **kwargs,
    )

    all_preprocessed_files = config.artefact_store["preprocessed_c"]
    config.artefact_store.add_c_build_files(all_preprocessed_files)

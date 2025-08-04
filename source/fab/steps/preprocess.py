##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran and C Preprocessing.

"""
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Tuple, Union

from fab.artefacts import (ArtefactSet, ArtefactsGetter, SuffixFilter,
                           CollectionGetter)
from fab.build_config import BuildConfig, FlagsConfig
from fab.metrics import send_metric
from fab.steps import check_for_errors, run_mp, step
from fab.tools import Category, Cpp, CppFortran, Preprocessor
from fab.util import (log_or_dot_finish, input_to_output_fpath, log_or_dot,
                      suffix_filter, Timer, by_type)

logger = logging.getLogger(__name__)


@dataclass
class MpCommonArgs():
    """Common args for calling process_artefact() using multiprocessing."""
    config: BuildConfig
    output_suffix: str
    preprocessor: Preprocessor
    flags: FlagsConfig
    name: str


def pre_processor(config: BuildConfig, preprocessor: Preprocessor,
                  files: Collection[Path],
                  output_collection: Union[str, ArtefactSet],
                  output_suffix,
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

    logger.info(f"preprocessor is '{preprocessor.name}'.")

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
    config.artefact_store.add(output_collection, set(by_type(results, Path)))


def process_artefact(arg: Tuple[Path, MpCommonArgs]):
    """
    Expects an input file in the source folder.
    Writes the output file to the output folder, with a lower case extension.

    """
    input_fpath, args = arg

    with Timer() as timer:
        output_fpath = (input_to_output_fpath(config=args.config,
                                              input_path=input_fpath)
                        .with_suffix(args.output_suffix))

        # already preprocessed?
        # todo: remove reuse_artefacts everywhere!
        if args.config.reuse_artefacts and output_fpath.exists():
            log_or_dot(logger, f'Preprocessor skipping: {input_fpath}')
        else:
            output_fpath.parent.mkdir(parents=True, exist_ok=True)

            params = args.flags.flags_for_path(path=input_fpath, config=args.config)

            log_or_dot(logger, f"PreProcessor running with parameters: "
                               f"'{' '.join(params)}'.'")
            try:
                args.preprocessor.preprocess(input_fpath, output_fpath, params)
            except Exception as err:
                raise Exception(f"error preprocessing {input_fpath}:\n"
                                f"{err}") from err

    send_metric(args.name, str(input_fpath), {'time_taken': timer.taken, 'start': timer.start})
    return output_fpath


# todo: rename preprocess_fortran
@step
def preprocess_fortran(config: BuildConfig, source: Optional[ArtefactsGetter] = None, **kwargs):
    """
    Wrapper to pre_processor for Fortran files.

    Ensures all preprocessed files are in the build output.
    This means *copying* already preprocessed files from source to build output.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.

    If source is not provided, it defaults to
    `SuffixFilter(ArtefactStore.FORTRAN_BUILD_FILES, '.F90')`.

    """
    if source:
        source_files = source(config.artefact_store)
    else:
        source_files = config.artefact_store[ArtefactSet.FORTRAN_BUILD_FILES]
    F90s = suffix_filter(source_files, '.F90')
    f90s = suffix_filter(source_files, '.f90')

    fpp = config.tool_box[Category.FORTRAN_PREPROCESSOR]
    if not isinstance(fpp, CppFortran):
        raise RuntimeError(f"Unexpected tool '{fpp.name}' of type "
                           f"'{type(fpp)}' instead of CppFortran")

    try:
        common_flags = kwargs.pop('common_flags')
    except KeyError:
        common_flags = []

    # preprocess big F90s
    pre_processor(
        config,
        preprocessor=fpp,
        common_flags=common_flags,
        files=F90s,
        output_collection=ArtefactSet.PREPROCESSED_FORTRAN,
        output_suffix='.f90',
        name='preprocess fortran',
        **kwargs,
    )

    config.artefact_store.replace(ArtefactSet.FORTRAN_BUILD_FILES,
                                  remove_files=F90s,
                                  add_files=config.artefact_store[ArtefactSet.PREPROCESSED_FORTRAN])

    # todo: parallel copy?
    # copy little f90s from source to output folder
    logger.info(f'Fortran preprocessor copying {len(f90s)} files to build_output')
    new_files = []
    remove_files = []
    for f90 in f90s:
        output_path = input_to_output_fpath(config, input_path=f90)
        if output_path != f90:
            if not output_path.parent.exists():
                output_path.parent.mkdir(parents=True)
            log_or_dot(logger, f'copying {f90}')
            shutil.copyfile(str(f90), str(output_path))
            # Only remove and add a file when it is actually copied.
            remove_files.append(f90)
            new_files.append(output_path)

    config.artefact_store.replace(ArtefactSet.FORTRAN_BUILD_FILES,
                                  remove_files=remove_files,
                                  add_files=new_files)


class DefaultCPreprocessorSource(ArtefactsGetter):
    """
    A source getter specifically for c preprocessing.
    Looks for the default output from pragma injection, falls back to default source finder.
    This allows the step to work with or without a preceding pragma step.

    """
    def __call__(self, artefact_store):
        return CollectionGetter(ArtefactSet.PRAGMAD_C)(artefact_store) \
               or SuffixFilter(ArtefactSet.INITIAL_SOURCE, '.c')(artefact_store)


# todo: rename preprocess_c
@step
def preprocess_c(config: BuildConfig,
                 source: Optional[ArtefactsGetter] = None, **kwargs):
    """
    Wrapper to pre_processor for C files.

    Params as per :func:`~fab.steps.preprocess._pre_processor`.
    If source is not provided, it defaults to
    :class:`~fab.steps.preprocess.DefaultCPreprocessorSource`.

    """
    source_getter = source or DefaultCPreprocessorSource()
    source_files = source_getter(config.artefact_store)
    cpp = config.tool_box[Category.C_PREPROCESSOR]
    if not isinstance(cpp, Cpp):
        raise RuntimeError(f"Unexpected tool '{cpp.name}' of type "
                           f"'{type(cpp)}' instead of Cpp")

    pre_processor(
        config,
        preprocessor=cpp,
        files=source_files,
        output_collection=ArtefactSet.PREPROCESSED_C,
        output_suffix='.c',
        name='preprocess c',
        **kwargs,
    )

    config.artefact_store.replace(ArtefactSet.C_BUILD_FILES,
                                  remove_files=source_files,
                                  add_files=config.artefact_store[ArtefactSet.PREPROCESSED_C])

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
C file compilation.

"""
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from fab import FabException
from fab.artefacts import ArtefactsGetter, FilterBuildTrees
from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import OBJECT_FILES
from fab.metrics import send_metric
from fab.parse.c import AnalysedC
from fab.steps import check_for_errors, run_mp, step
from fab.tools import Categories, Flags
from fab.util import CompiledFile, log_or_dot, Timer, by_type

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.c')
DEFAULT_OUTPUT_ARTEFACT = ''


@dataclass
class MpCommonArgs():
    '''A simple class to pass arguments to subprocesses.'''
    config: BuildConfig
    flags: FlagsConfig


@step
def compile_c(config, common_flags: Optional[List[str]] = None,
              path_flags: Optional[List] = None, source: Optional[ArtefactsGetter] = None):
    """
    Compiles all C files in all build trees, creating or extending a set of compiled files for each target.

    This step uses multiprocessing.
    All C files are compiled in a single pass.


    Uses multiprocessing, unless disabled in the *config*.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param common_flags:
        A list of strings to be included in the command line call, for all files.
    :param path_flags:
        A list of :class:`~fab.build_config.AddFlags`, defining flags to be included in the command line call
        for selected files.
    :param source:
        An :class:`~fab.artefacts.ArtefactsGetter` which give us our c files to process.

    """
    # todo: tell the compiler (and other steps) which artefact name to create?

    compiler = config.tool_box[Categories.C_COMPILER]
    logger.info(f'c compiler is {compiler}')

    env_flags = os.getenv('CFLAGS', '').split()
    common_flags = env_flags + (common_flags or [])

    flags = FlagsConfig(common_flags=common_flags, path_flags=path_flags)
    source_getter = source or DEFAULT_SOURCE_GETTER

    # gather all the source to compile, for all build trees, into one big lump
    build_lists: Dict = source_getter(config.artefact_store)
    to_compile: list = sum(build_lists.values(), [])
    logger.info(f"compiling {len(to_compile)} c files")

    mp_payload = MpCommonArgs(config=config, flags=flags)
    mp_items = [(fpath, mp_payload) for fpath in to_compile]

    # compile everything in one go
    compilation_results = run_mp(config, items=mp_items, func=_compile_file)
    check_for_errors(compilation_results, caller_label='compile c')
    compiled_c = list(by_type(compilation_results, CompiledFile))
    logger.info(f"compiled {len(compiled_c)} c files")

    # record the prebuild files as being current, so the cleanup knows not to delete them
    prebuild_files = {r.output_fpath for r in compiled_c}
    config.add_current_prebuilds(prebuild_files)

    # record the compilation results for the next step
    store_artefacts(compiled_c, build_lists, config.artefact_store)


# todo: very similar code in fortran compiler
def store_artefacts(compiled_files: List[CompiledFile], build_lists: Dict[str, List], artefact_store):
    """
    Create our artefact collection; object files for each compiled file, per root symbol.

    """
    # add the new object files to the artefact store, by target
    lookup = {c.input_fpath: c for c in compiled_files}
    object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
    for root, source_files in build_lists.items():
        new_objects = [lookup[af.fpath].output_fpath for af in source_files]
        object_files[root].update(new_objects)


def _compile_file(arg: Tuple[AnalysedC, MpCommonArgs]):

    analysed_file, mp_payload = arg
    config = mp_payload.config
    compiler = config.tool_box[Categories.C_COMPILER]
    with Timer() as timer:
        flags = Flags(mp_payload.flags.flags_for_path(path=analysed_file.fpath,
                                                      config=config))
        obj_combo_hash = _get_obj_combo_hash(compiler, analysed_file, flags)

        obj_file_prebuild = config.prebuild_folder / f'{analysed_file.fpath.stem}.{obj_combo_hash:x}.o'

        # prebuild available?
        if obj_file_prebuild.exists():
            log_or_dot(logger, f'CompileC using prebuild: {analysed_file.fpath}')
        else:
            obj_file_prebuild.parent.mkdir(parents=True, exist_ok=True)
            log_or_dot(logger, f'CompileC compiling {analysed_file.fpath}')
            try:
                compiler.compile_file(analysed_file.fpath, obj_file_prebuild,
                                      add_flags=flags)
            except Exception as err:
                return FabException(f"error compiling {analysed_file.fpath}:\n{err}")

    send_metric(
        group="compile c",
        name=str(analysed_file.fpath),
        value={'time_taken': timer.taken, 'start': timer.start})
    return CompiledFile(input_fpath=analysed_file.fpath, output_fpath=obj_file_prebuild)


def _get_obj_combo_hash(compiler, analysed_file, flags: Flags):
    # get a combo hash of things which matter to the object file we define
    try:
        obj_combo_hash = sum([
            analysed_file.file_hash,
            flags.checksum(),
            compiler.get_hash(),
        ])
    except TypeError:
        raise ValueError("could not generate combo hash for object file")
    return obj_combo_hash

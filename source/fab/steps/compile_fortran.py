##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""

import logging
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional, Union

from fab.artefacts import ArtefactsGetter, ArtefactStore, FilterBuildTrees
from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import OBJECT_FILES
from fab.metrics import send_metric
from fab.parse.fortran import AnalysedFortran
from fab.steps import check_for_errors, run_mp, step
from fab.tools import Categories, Compiler, Flags
from fab.util import (CompiledFile, log_or_dot_finish, log_or_dot, Timer,
                      by_type, file_checksum)

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')


@dataclass
class MpCommonArgs():
    """Arguments to be passed into the multiprocessing function, alongside the filenames."""
    config: BuildConfig
    flags: FlagsConfig
    mod_hashes: Dict[str, int]
    syntax_only: bool


@step
def compile_fortran(config: BuildConfig, common_flags: Optional[List[str]] = None,
                    path_flags: Optional[List] = None, source: Optional[ArtefactsGetter] = None):
    """
    Compiles all Fortran files in all build trees, creating/extending a set of compiled files for each build target.

    Files are compiled in multiple passes, with each pass enabling further files to be compiled in the next pass.

    Uses multiprocessing, unless disabled in the config.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param common_flags:
        A list of strings to be included in the command line call, for all files.
    :param path_flags:
        A list of :class:`~fab.build_config.AddFlags`, defining flags to be included in the command line call
        for selected files.
    :param source:
        An :class:`~fab.artefacts.ArtefactsGetter` which gives us our Fortran files to process.

    """

    compiler, flags_config = handle_compiler_args(config, common_flags,
                                                  path_flags)
    # Set module output folder:
    compiler.set_module_output_path(config.build_output)

    source_getter = source or DEFAULT_SOURCE_GETTER
    mod_hashes: Dict[str, int] = {}

    # get all the source to compile, for all build trees, into one big lump
    build_lists: Dict[str, List] = source_getter(config.artefact_store)

    syntax_only = compiler.has_syntax_only and config.two_stage
    # build the arguments passed to the multiprocessing function
    mp_common_args = MpCommonArgs(
        config=config, flags=flags_config,
        mod_hashes=mod_hashes, syntax_only=syntax_only)

    # compile everything in multiple passes
    compiled: Dict[Path, CompiledFile] = {}
    uncompiled: Set[AnalysedFortran] = set(sum(build_lists.values(), []))
    logger.info(f"compiling {len(uncompiled)} fortran files")

    if syntax_only:
        logger.info("Starting two-stage compile: mod files, multiple passes")
    elif config.two_stage:
        logger.info(f"Compiler {compiler.name} does not support syntax-only, "
                    f"disabling two-stage compile.")

    while uncompiled:
        uncompiled = compile_pass(config=config, compiled=compiled, uncompiled=uncompiled,
                                  mp_common_args=mp_common_args, mod_hashes=mod_hashes)
    log_or_dot_finish(logger)

    if syntax_only:
        logger.info("Finalising two-stage compile: object files, single pass")
        mp_common_args.syntax_only = False

        # a single pass should now compile all the object files in one go
        uncompiled = set(sum(build_lists.values(), []))  # todo: order by last compile duration
        mp_args = [(fpath, mp_common_args) for fpath in uncompiled]
        results_this_pass = run_mp(config, items=mp_args, func=process_file)
        log_or_dot_finish(logger)
        check_for_errors(results_this_pass, caller_label="compile_fortran")
        compiled_this_pass = list(by_type(results_this_pass, CompiledFile))
        logger.info(f"stage 2 compiled {len(compiled_this_pass)} files")

    # record the compilation results for the next step
    store_artefacts(compiled, build_lists, config.artefact_store)


def handle_compiler_args(config: BuildConfig, common_flags=None,
                         path_flags=None):

    # Command line tools are sometimes specified with flags attached.
    compiler = config.tool_box[Categories.FORTRAN_COMPILER]
    logger.info(f'fortran compiler is {compiler} {compiler.get_version()}')

    # Collate the flags from 1) flags env and 2) parameters.
    env_flags = os.getenv('FFLAGS', '').split()
    common_flags = env_flags + (common_flags or [])
    flags_config = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

    return compiler, flags_config


def compile_pass(config, compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFortran],
                 mp_common_args: MpCommonArgs, mod_hashes: Dict[str, int]):

    # what can we compile next?
    compile_next = get_compile_next(compiled, uncompiled)

    # compile
    logger.info(f"\ncompiling {len(compile_next)} of {len(uncompiled)} remaining files")
    mp_args = [(fpath, mp_common_args) for fpath in compile_next]
    results_this_pass = run_mp(config, items=mp_args, func=process_file)

    # there's a compilation result and a list of prebuild files for each compiled file
    compilation_results, prebuild_files = zip(*results_this_pass) if results_this_pass else (tuple(), tuple())
    check_for_errors(compilation_results, caller_label="compile_pass")
    compiled_this_pass = list(by_type(compilation_results, CompiledFile))
    logger.debug(f"compiled {len(compiled_this_pass)} files")

    # record the prebuild files as being current, so the cleanup knows not to delete them
    config.add_current_prebuilds(chain(*prebuild_files))

    # hash the modules we just created
    new_mod_hashes = get_mod_hashes(compile_next, config)
    mod_hashes.update(new_mod_hashes)

    # add compiled files to all compiled files
    compiled.update({cf.input_fpath: cf for cf in compiled_this_pass})

    # remove compiled files from remaining files
    uncompiled = set(filter(lambda af: af.fpath not in compiled, uncompiled))
    return uncompiled


def get_compile_next(compiled: Dict[Path, CompiledFile], uncompiled: Set[AnalysedFortran]) \
        -> Set[AnalysedFortran]:

    # find what to compile next
    compile_next = set()
    not_ready: Dict[Path, List[Path]] = {}
    for af in uncompiled:
        # all deps ready?
        unfulfilled = [dep for dep in af.file_deps if dep not in compiled and dep.suffix == '.f90']
        if unfulfilled:
            not_ready[af.fpath] = unfulfilled
        else:
            compile_next.add(af)

    # unable to compile anything?
    if len(uncompiled) and not compile_next:
        msg = 'Nothing more can be compiled due to unfulfilled dependencies:\n'
        for f, unf in not_ready.items():
            msg += f'\n\n{f}'
            for u in unf:
                msg += f'\n    {str(u)}'

        raise ValueError(msg)

    return compile_next


def store_artefacts(compiled_files: Dict[Path, CompiledFile],
                    build_lists: Dict[str, List],
                    artefact_store: ArtefactStore):
    """
    Create our artefact collection; object files for each compiled file, per root symbol.

    """
    # add the new object files to the artefact store, by target
    lookup = {c.input_fpath: c for c in compiled_files.values()}
    object_files = artefact_store.setdefault(OBJECT_FILES, defaultdict(set))
    for root, source_files in build_lists.items():
        new_objects = [lookup[af.fpath].output_fpath for af in source_files]
        object_files[root].update(new_objects)


def process_file(arg: Tuple[AnalysedFortran, MpCommonArgs]) \
        -> Union[Tuple[CompiledFile, List[Path]], Tuple[Exception, None]]:
    """
    Prepare to compile a fortran file, and compile it if anything has changed since it was last compiled.

    Object files are created directly as artefacts in the prebuild folder.
    Mod files are created in the module folder and copied as artefacts into the prebuild folder.
    If nothing has changed, prebuilt mod files are copied *from* the prebuild folder into the module folder.

    .. note::

        Prebuild filenames include a "combo-hash" of everything that, if changed, must trigger a recompile.
        For mod and object files, this includes a checksum of: *source code, compiler*.
        For object files, this also includes a checksum of: *compiler flags, modules on which we depend*.

        Before compiling a file, we calculate the combo hashes and see if the output files already exists.

    Returns a compilation result, regardless of whether it was compiled or prebuilt.

    """
    with Timer() as timer:
        analysed_file, mp_common_args = arg
        config = mp_common_args.config
        compiler = config.tool_box[Categories.FORTRAN_COMPILER]
        flags = Flags(mp_common_args.flags.flags_for_path(path=analysed_file.fpath, config=config))

        mod_combo_hash = _get_mod_combo_hash(analysed_file, compiler=compiler)
        obj_combo_hash = _get_obj_combo_hash(analysed_file,
                                             mp_common_args=mp_common_args,
                                             compiler=compiler, flags=flags)

        # calculate the incremental/prebuild artefact filenames
        obj_file_prebuild = mp_common_args.config.prebuild_folder / f'{analysed_file.fpath.stem}.{obj_combo_hash:x}.o'
        mod_file_prebuilds = [
            mp_common_args.config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod'
            for mod_def in analysed_file.module_defs
        ]

        # have we got all the prebuilt artefacts we need to avoid a recompile?
        prebuilds_exist = list(map(lambda f: f.exists(), [obj_file_prebuild] + mod_file_prebuilds))
        if not all(prebuilds_exist):
            # compile
            try:
                logger.debug(f'CompileFortran compiling {analysed_file.fpath}')
                compile_file(analysed_file.fpath, flags,
                             output_fpath=obj_file_prebuild,
                             mp_common_args=mp_common_args)
            except Exception as err:
                return Exception(f"Error compiling {analysed_file.fpath}:\n{err}"), None

            # copy the mod files to the prebuild folder as artefacts for reuse
            # note: perhaps we could sometimes avoid these copies because mods can change less frequently than obj
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    mp_common_args.config.build_output / f'{mod_def}.mod',
                    mp_common_args.config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                )

        else:
            log_or_dot(logger, f'CompileFortran using prebuild: {analysed_file.fpath}')

            # copy the prebuilt mod files from the prebuild folder
            for mod_def in analysed_file.module_defs:
                shutil.copy2(
                    mp_common_args.config.prebuild_folder / f'{mod_def}.{mod_combo_hash:x}.mod',
                    mp_common_args.config.build_output / f'{mod_def}.mod',
                )

        # return the results
        compiled_file = CompiledFile(input_fpath=analysed_file.fpath, output_fpath=obj_file_prebuild)
        artefacts = [obj_file_prebuild] + mod_file_prebuilds

    metric_name = "compile fortran"
    if mp_common_args.syntax_only:
        metric_name += " syntax-only"

    send_metric(
        group=metric_name,
        name=str(analysed_file.fpath),
        value={'time_taken': timer.taken, 'start': timer.start})

    return compiled_file, artefacts


def _get_obj_combo_hash(analysed_file, mp_common_args: MpCommonArgs,
                        compiler: Compiler, flags: Flags):
    # get a combo hash of things which matter to the object file we define
    # todo: don't just silently use 0 for a missing dep hash
    mod_deps_hashes = {
        mod_dep: mp_common_args.mod_hashes.get(mod_dep, 0) for mod_dep in analysed_file.module_deps}
    try:
        obj_combo_hash = sum([
            analysed_file.file_hash,
            flags.checksum(),
            sum(mod_deps_hashes.values()),
            compiler.get_hash(),
        ])
    except TypeError:
        raise ValueError("could not generate combo hash for object file")
    return obj_combo_hash


def _get_mod_combo_hash(analysed_file, compiler: Compiler):
    # get a combo hash of things which matter to the mod files we define
    try:
        mod_combo_hash = sum([
            analysed_file.file_hash,
            compiler.get_hash(),
        ])
    except TypeError:
        raise ValueError("could not generate combo hash for mod files")
    return mod_combo_hash


def compile_file(analysed_file, flags, output_fpath, mp_common_args):
    """
    Call the compiler.

    The current working folder for the command is set to the folder where the
    source file lives when compile_file is called. This is done to stop the
    compiler inserting folder information into the mod files, which would
    cause them to have different checksums depending on where they live.

    """
    output_fpath.parent.mkdir(parents=True, exist_ok=True)

    # tool
    config = mp_common_args.config
    compiler = config.tool_box[Categories.FORTRAN_COMPILER]

    compiler.compile_file(input_file=analysed_file, output_file=output_fpath,
                          add_flags=flags,
                          syntax_only=mp_common_args.syntax_only)


def get_mod_hashes(analysed_files: Set[AnalysedFortran], config) -> Dict[str, int]:
    """
    Get the hash of every module file defined in the list of analysed files.

    """
    mod_hashes = {}
    for af in analysed_files:
        for mod_def in af.module_defs:
            fpath: Path = config.build_output / f'{mod_def}.mod'
            mod_hashes[mod_def] = file_checksum(fpath).file_hash

    return mod_hashes

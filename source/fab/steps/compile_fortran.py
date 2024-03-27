##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fortran file compilation.

"""

# TODO: This has become too complicated. Refactor.


import logging
import os
import shutil
import zlib
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional, Union

from fab.artefacts import ArtefactsGetter, FilterBuildTrees
from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import OBJECT_FILES
from fab.metrics import send_metric
from fab.parse.fortran import AnalysedFortran
from fab.steps import check_for_errors, run_mp, step
from fab.tools import COMPILERS, remove_managed_flags, flags_checksum, run_command, get_tool, get_compiler_version
from fab.util import CompiledFile, log_or_dot_finish, log_or_dot, Timer, by_type, \
    file_checksum

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = FilterBuildTrees(suffix='.f90')


@dataclass
class MpCommonArgs(object):
    """Arguments to be passed into the multiprocessing function, alongside the filenames."""
    config: BuildConfig
    flags: FlagsConfig
    compiler: str
    compiler_version: str
    mod_hashes: Dict[str, int]
    two_stage_flag: Optional[str]
    stage: Optional[int]


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

    compiler, compiler_version, flags_config = handle_compiler_args(common_flags, path_flags)

    source_getter = source or DEFAULT_SOURCE_GETTER

    # todo: move this to the known compiler flags?
    # todo: this is a misleading name
    two_stage_flag = None
    if compiler == 'gfortran' and config.two_stage:
        two_stage_flag = '-fsyntax-only'

    mod_hashes: Dict[str, int] = {}

    # get all the source to compile, for all build trees, into one big lump
    build_lists: Dict[str, List] = source_getter(config.artefact_store)

    # build the arguments passed to the multiprocessing function
    mp_common_args = MpCommonArgs(
        config=config, flags=flags_config, compiler=compiler, compiler_version=compiler_version,
        mod_hashes=mod_hashes, two_stage_flag=two_stage_flag, stage=None)

    # compile everything in multiple passes
    compiled: Dict[Path, CompiledFile] = {}
    uncompiled: Set[AnalysedFortran] = set(sum(build_lists.values(), []))
    logger.info(f"compiling {len(uncompiled)} fortran files")

    if two_stage_flag:
        logger.info("Starting two-stage compile: mod files, multiple passes")
        mp_common_args.stage = 1

    while uncompiled:
        uncompiled = compile_pass(config=config, compiled=compiled, uncompiled=uncompiled,
                                  mp_common_args=mp_common_args, mod_hashes=mod_hashes)
    log_or_dot_finish(logger)

    if two_stage_flag:
        logger.info("Finalising two-stage compile: object files, single pass")
        mp_common_args.stage = 2

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


def handle_compiler_args(common_flags=None, path_flags=None):

    # Command line tools are sometimes specified with flags attached.
    compiler, compiler_flags = get_fortran_compiler()

    compiler_version = get_compiler_version(compiler)
    logger.info(f'fortran compiler is {compiler} {compiler_version}')

    # collate the flags from 1) compiler env, 2) flags env and 3) params
    env_flags = os.getenv('FFLAGS', '').split()
    common_flags = compiler_flags + env_flags + (common_flags or [])

    # Do we know this compiler? If so we can manage the flags a little, to avoid duplication or misconfiguration.
    # todo: This has been raised for discussion - we might never want to modify incoming flags...
    known_compiler = COMPILERS.get(os.path.basename(compiler))
    if known_compiler:
        common_flags = remove_managed_flags(compiler, common_flags)
    else:
        logger.warning(f"Unknown compiler {compiler}. Fab cannot control certain flags."
                       "Please ensure you specify the flag `-c` equivalent flag to only compile."
                       "Please ensure the module output folder is set to your config's build_output folder."
                       "or please extend fab.tools.COMPILERS in your build script.")

    flags_config = FlagsConfig(common_flags=common_flags, path_flags=path_flags)

    return compiler, compiler_version, flags_config


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


def store_artefacts(compiled_files: Dict[Path, CompiledFile], build_lists: Dict[str, List], artefact_store):
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

        flags = mp_common_args.flags.flags_for_path(path=analysed_file.fpath, config=mp_common_args.config)
        mod_combo_hash = _get_mod_combo_hash(analysed_file, mp_common_args=mp_common_args)
        obj_combo_hash = _get_obj_combo_hash(analysed_file, mp_common_args=mp_common_args, flags=flags)

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
                compile_file(analysed_file, flags, output_fpath=obj_file_prebuild, mp_common_args=mp_common_args)
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

    # todo: probably better to record both mod and obj metrics
    metric_name = "compile fortran" + (f' stage {mp_common_args.stage}' if mp_common_args.stage else '')
    send_metric(
        group=metric_name,
        name=str(analysed_file.fpath),
        value={'time_taken': timer.taken, 'start': timer.start})

    return compiled_file, artefacts


def _get_obj_combo_hash(analysed_file, mp_common_args: MpCommonArgs, flags):
    # get a combo hash of things which matter to the object file we define
    # todo: don't just silently use 0 for a missing dep hash
    mod_deps_hashes = {
        mod_dep: mp_common_args.mod_hashes.get(mod_dep, 0) for mod_dep in analysed_file.module_deps}
    try:
        obj_combo_hash = sum([
            analysed_file.file_hash,
            flags_checksum(flags),
            sum(mod_deps_hashes.values()),
            zlib.crc32(mp_common_args.compiler.encode()),
            zlib.crc32(mp_common_args.compiler_version.encode()),
        ])
    except TypeError:
        raise ValueError("could not generate combo hash for object file")
    return obj_combo_hash


def _get_mod_combo_hash(analysed_file, mp_common_args: MpCommonArgs):
    # get a combo hash of things which matter to the mod files we define
    try:
        mod_combo_hash = sum([
            analysed_file.file_hash,
            zlib.crc32(mp_common_args.compiler.encode()),
            zlib.crc32(mp_common_args.compiler_version.encode()),
        ])
    except TypeError:
        raise ValueError("could not generate combo hash for mod files")
    return mod_combo_hash


def compile_file(analysed_file, flags, output_fpath, mp_common_args):
    """
    Call the compiler.

    The current working folder for the command is set to the folder where the source file lives.
    This is done to stop the compiler inserting folder information into the mod files,
    which would cause them to have different checksums depending on where they live.

    """
    output_fpath.parent.mkdir(parents=True, exist_ok=True)

    # tool
    command = [mp_common_args.compiler]
    known_compiler = COMPILERS.get(os.path.basename(mp_common_args.compiler))

    # Compile flag.
    # If it's an unknown compiler, we rely on the user config to specify this.
    if known_compiler:
        command.append(known_compiler.compile_flag)

    # flags
    command.extend(flags)
    if mp_common_args.two_stage_flag and mp_common_args.stage == 1:
        command.append(mp_common_args.two_stage_flag)

    # Module folder.
    # If it's an unknown compiler, we rely on the user config to specify this.
    if known_compiler:
        command.extend([known_compiler.module_folder_flag, str(mp_common_args.config.build_output)])

    # files
    command.append(analysed_file.fpath.name)
    command.extend(['-o', str(output_fpath)])

    run_command(command, cwd=analysed_file.fpath.parent)


# todo: move this


def get_fortran_compiler(compiler: Optional[str] = None):
    """
    Get the fortran compiler specified by the `$FC` environment variable,
    or overridden by the optional `compiler` argument.

    Separates the tool and flags for the sort of value we see in environment variables, e.g. `gfortran -c`.

    :param compiler:
        Use this string instead of the $FC environment variable.

    Returns the tool and a list of flags.

    """
    fortran_compiler = None
    try:
        fortran_compiler = get_tool(compiler or os.getenv('FC', ''))  # type: ignore
    except ValueError:
        # tool not specified
        pass

    if not fortran_compiler:
        try:
            run_command(['gfortran', '--help'])
            fortran_compiler = 'gfortran', []
            logger.info('detected gfortran')
        except RuntimeError:
            # gfortran not available
            pass

    if not fortran_compiler:
        try:
            run_command(['ifort', '--help'])
            fortran_compiler = 'ifort', []
            logger.info('detected ifort')
        except RuntimeError:
            # gfortran not available
            pass

    if not fortran_compiler:
        raise RuntimeError('no fortran compiler specified or discovered')

    return fortran_compiler


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

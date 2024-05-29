# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A preprocessor and code generation step for PSyclone.
https://github.com/stfc/PSyclone

"""
from dataclasses import dataclass
import logging
import re
import shutil
import warnings
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Callable

from fab.build_config import BuildConfig

from fab.artefacts import ArtefactsGetter, CollectionConcat, SuffixFilter
from fab.parse.fortran import FortranAnalyser, AnalysedFortran
from fab.parse.x90 import X90Analyser, AnalysedX90
from fab.steps import run_mp, check_for_errors, step
from fab.steps.preprocess import pre_processor
from fab.tools import Categories
from fab.util import log_or_dot, input_to_output_fpath, file_checksum, file_walk, TimerLogger, \
    string_checksum, suffix_filter, by_type, log_or_dot_finish

logger = logging.getLogger(__name__)


# todo: should this be part of the psyclone step?
def preprocess_x90(config, common_flags: Optional[List[str]] = None):
    common_flags = common_flags or []

    # get the tool from FPP
    fpp = config.tool_box[Categories.FORTRAN_PREPROCESSOR]
    source_files = SuffixFilter('all_source', '.X90')(config.artefact_store)

    pre_processor(
        config,
        preprocessor=fpp,
        files=source_files,
        output_collection='preprocessed_x90',
        output_suffix='.x90',
        name='preprocess x90',
        common_flags=common_flags,
    )


@dataclass
class MpCommonArgs:
    """
    Runtime data for child processes to read.

    Contains data used to calculate the prebuild hash.

    """
    config: BuildConfig
    analysed_x90: Dict[Path, AnalysedX90]

    kernel_roots: List[Path]
    transformation_script: Optional[Callable[[Path, BuildConfig], Path]]
    cli_args: List[str]

    all_kernel_hashes: Dict[str, int]
    overrides_folder: Optional[Path]
    override_files: List[str]  # filenames (not paths) of hand crafted overrides


DEFAULT_SOURCE_GETTER = CollectionConcat([
    'preprocessed_x90',  # any X90 we've preprocessed this run
    SuffixFilter('all_source', '.x90'),  # any already preprocessed x90 we pulled in
])


@step
def psyclone(config, kernel_roots: Optional[List[Path]] = None,
             transformation_script: Optional[Callable[[Path, BuildConfig], Path]] = None,
             cli_args: Optional[List[str]] = None,
             source_getter: Optional[ArtefactsGetter] = None,
             overrides_folder: Optional[Path] = None):
    """
    Psyclone runner step.

    .. note::

        This step produces Fortran, so it must be run before the :class:`~fab.steps.analyse.Analyse` step.

    This step stores prebuilt results to speed up subsequent builds.
    To generate the prebuild hashes, it analyses the X90 and kernel files, storing prebuilt results for these also.

    Kernel files are just normal Fortran, and the standard Fortran analyser is used to analyse them

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param kernel_roots:
        Folders containing kernel files. Must be part of the analysed source code.
    :param transformation_script:
        The function to get Python transformation script.
        It takes in a file path and the config object, and returns the path of the transformation script or None.
        If no function is given or the function returns None, no script will be applied and PSyclone still runs.
    :param cli_args:
        Passed through to the psyclone cli tool.
    :param source_getter:
        Optional override for getting input files from the artefact store.
    :param overrides_folder:
        Optional folder containing hand-crafted override files.
        Must be part of the subsequently analysed source code.
        Any file produced by psyclone will be deleted if there is a corresponding file in this folder.
    """
    kernel_roots = kernel_roots or []

    # "the gross switch which turns off MPI usage is a command-line argument"
    cli_args = cli_args or []

    source_getter = source_getter or DEFAULT_SOURCE_GETTER
    x90s = source_getter(config.artefact_store)

    # analyse the x90s
    analysed_x90 = _analyse_x90s(config, x90s)

    # analyse the kernel files,
    all_kernel_hashes = _analyse_kernels(config, kernel_roots)

    # get the data in a payload object for child processes to calculate prebuild hashes
    mp_payload = _generate_mp_payload(
        config, analysed_x90, all_kernel_hashes, overrides_folder, kernel_roots, transformation_script, cli_args)

    # run psyclone.
    # for every file, we get back a list of its output files plus a list of the prebuild copies.
    mp_arg = [(x90, mp_payload) for x90 in x90s]
    with TimerLogger(f"running psyclone on {len(x90s)} x90 files"):
        results = run_mp(config, mp_arg, do_one_file)
    log_or_dot_finish(logger)
    outputs, prebuilds = zip(*results) if results else ((), ())
    check_for_errors(outputs, caller_label='psyclone')

    # flatten the list of lists we got back from run_mp
    output_files: List[Path] = list(chain(*by_type(outputs, List)))
    prebuild_files: List[Path] = list(chain(*by_type(prebuilds, List)))

    # record the output files in the artefact store for further processing
    config.artefact_store['psyclone_output'] = output_files
    outputs_str = "\n".join(map(str, output_files))
    logger.debug(f'psyclone outputs:\n{outputs_str}\n')

    # mark the prebuild files as being current so the cleanup step doesn't delete them
    config.add_current_prebuilds(prebuild_files)
    prebuilds_str = "\n".join(map(str, prebuild_files))
    logger.debug(f'psyclone prebuilds:\n{prebuilds_str}\n')

    # todo: delete any psy layer files which have hand-written overrides, in a given overrides folder
    # is this called psykal?
    # assert False


def _generate_mp_payload(config, analysed_x90, all_kernel_hashes, overrides_folder, kernel_roots,
                         transformation_script, cli_args) -> MpCommonArgs:
    override_files: List[str] = []
    if overrides_folder:
        override_files = [f.name for f in file_walk(overrides_folder)]

    return MpCommonArgs(
        config=config,
        kernel_roots=kernel_roots,
        transformation_script=transformation_script,
        cli_args=cli_args,
        analysed_x90=analysed_x90,
        all_kernel_hashes=all_kernel_hashes,
        overrides_folder=overrides_folder,
        override_files=override_files,
    )


def _analyse_x90s(config, x90s: Set[Path]) -> Dict[Path, AnalysedX90]:
    # Analyse parsable versions of the x90s, finding kernel dependencies.

    # make parsable - todo: fast enough not to require prebuilds?
    with TimerLogger(f"converting {len(x90s)} x90s into parsable fortran"):
        parsable_x90s = run_mp(config, items=x90s, func=make_parsable_x90)

    # parse
    x90_analyser = X90Analyser()
    x90_analyser._config = config
    with TimerLogger(f"analysing {len(parsable_x90s)} parsable x90 files"):
        x90_results = run_mp(config, items=parsable_x90s, func=x90_analyser.run)
    log_or_dot_finish(logger)
    x90_analyses, x90_artefacts = zip(*x90_results) if x90_results else ((), ())
    check_for_errors(results=x90_analyses)

    # mark the analysis results files (i.e. prebuilds) as being current, so the cleanup knows not to delete them
    prebuild_files = list(by_type(x90_artefacts, Path))
    config.add_current_prebuilds(prebuild_files)

    # record the analysis results against the original x90 filenames (not the parsable versions we analysed)
    analysed_x90 = by_type(x90_analyses, AnalysedX90)
    analysed_x90 = {result.fpath.with_suffix('.x90'): result for result in analysed_x90}

    # make the hashes from the original x90s, not the parsable versions which have invoke names removed.
    for p, r in analysed_x90.items():
        analysed_x90[p]._file_hash = file_checksum(p).file_hash

    return analysed_x90


def _analyse_kernels(config, kernel_roots) -> Dict[str, int]:
    """
    We want to hash the kernel metadata (type defs).

    Kernel metadata are type definitions passed to invoke().
    For example, this x90 code depends on the kernel `compute_total_mass_kernel_type`.
    .. code-block:: fortran

        call invoke( name = "compute_dry_mass",                                         &
                     compute_total_mass_kernel_type(dry_mass, rho, chi, panel_id, qr),  &
                     sum_X(total_dry, dry_mass))

    We can see this kernel in a use statement at the top of the x90.
    .. code-block:: fortran

        use compute_total_mass_kernel_mod,   only: compute_total_mass_kernel_type

    Some kernels, such as `setval_c`, are
    `PSyclone built-ins <https://github.com/stfc/PSyclone/blob/ebb7f1aa32a9377da6ccc1ec04eec4adbc1e0a0a/src/
    psyclone/domain/lfric/lfric_builtins.py#L2136>`_.
    They will not appear in use statements and can be ignored.

    The Psyclone and Analyse steps both use the generic Fortran analyser, which recognises Psyclone kernel metadata.
    The Analysis step must come after this step because it needs to analyse the fortran we create.

    """
    # Ignore the prebuild folder. Todo: test the prebuild folder is ignored, in case someone breaks this.
    file_lists = [list(file_walk(root, ignore_folders=[config.prebuild_folder])) for root in kernel_roots]
    all_kernel_files: Set[Path] = set(sum(file_lists, []))
    kernel_files: List[Path] = suffix_filter(all_kernel_files, ['.f90'])

    # We use the normal Fortran analyser, which records psyclone kernel metadata.
    # todo: We'd like to separate that from the general fortran analyser at some point, to reduce coupling.
    # The Analyse step also uses the same fortran analyser. It stores its results so they won't be analysed twice.
    fortran_analyser = FortranAnalyser()
    fortran_analyser._config = config
    with TimerLogger(f"analysing {len(kernel_files)} potential psyclone kernel files"):
        fortran_results = run_mp(config, items=kernel_files, func=fortran_analyser.run)
    log_or_dot_finish(logger)
    fortran_analyses, fortran_artefacts = zip(*fortran_results) if fortran_results else (tuple(), tuple())

    errors: List[Exception] = list(by_type(fortran_analyses, Exception))
    if errors:
        errs_str = '\n\n'.join(map(str, errors))
        logger.error(f"There were {len(errors)} errors while parsing kernels:\n\n{errs_str}")

    # mark the analysis results files (i.e. prebuilds) as being current, so the cleanup knows not to delete them
    prebuild_files = list(by_type(fortran_artefacts, Path))
    config.add_current_prebuilds(prebuild_files)

    analysed_fortran: List[AnalysedFortran] = list(by_type(fortran_analyses, AnalysedFortran))

    # gather all kernel hashes into one big lump
    all_kernel_hashes: Dict[str, int] = {}
    for af in analysed_fortran:
        assert set(af.psyclone_kernels).isdisjoint(all_kernel_hashes), \
            f"duplicate kernel name(s): {set(af.psyclone_kernels) & set(all_kernel_hashes)}"
        all_kernel_hashes.update(af.psyclone_kernels)

    return all_kernel_hashes


def do_one_file(arg: Tuple[Path, MpCommonArgs]):
    x90_file, mp_payload = arg
    prebuild_hash = _gen_prebuild_hash(x90_file, mp_payload)

    # These are the filenames we expect to be output for this x90 input file.
    # There will always be one modified_alg, and 0-1 generated psy file.
    modified_alg: Path = x90_file.with_suffix('.f90')
    modified_alg = input_to_output_fpath(config=mp_payload.config, input_path=modified_alg)
    psy_file: Path = x90_file.parent / (str(x90_file.stem) + '_psy.f90')
    psy_file = input_to_output_fpath(config=mp_payload.config, input_path=psy_file)

    psy_file.parent.mkdir(parents=True, exist_ok=True)

    # do we already have prebuilt results for this x90 file?
    prebuilt_alg, prebuilt_gen = _get_prebuild_paths(
        mp_payload.config.prebuild_folder, modified_alg, psy_file, prebuild_hash)
    if prebuilt_alg.exists():
        # todo: error handling in here
        msg = f'found prebuilds for {x90_file}:\n    {prebuilt_alg}'
        shutil.copy2(prebuilt_alg, modified_alg)
        if prebuilt_gen.exists():
            msg += f'\n    {prebuilt_gen}'
            shutil.copy2(prebuilt_gen, psy_file)
        log_or_dot(logger=logger, msg=msg)

    else:
        config = mp_payload.config
        psyclone = config.tool_box[Categories.PSYCLONE]
        try:
            transformation_script = mp_payload.transformation_script
            logger.info(f"running psyclone on '{x90_file}'.")
            psyclone.process(config=mp_payload.config,
                             api="dynamo0.3",
                             x90_file=x90_file,
                             psy_file=psy_file,
                             alg_file=modified_alg,
                             transformation_script=transformation_script,
                             kernel_roots=mp_payload.kernel_roots,
                             additional_parameters=mp_payload.cli_args)

            shutil.copy2(modified_alg, prebuilt_alg)
            msg = f'created prebuilds for {x90_file}:\n    {prebuilt_alg}'
            if Path(psy_file).exists():
                msg += f'\n    {prebuilt_gen}'
                shutil.copy2(psy_file, prebuilt_gen)
            log_or_dot(logger=logger, msg=msg)

        except Exception as err:
            logger.error(err)
            return err, None

    # do we have handwritten overrides for either of the files we just created?
    modified_alg = _check_override(modified_alg, mp_payload)
    psy_file = _check_override(psy_file, mp_payload)

    # return the output files from psyclone
    result: List[Path] = [modified_alg]
    if Path(psy_file).exists():
        result.append(psy_file)

    # we also want to return the prebuild artefact files we created,
    # which are just copies, in the prebuild folder, with hashes in the filenames.
    prebuild_result: List[Path] = [prebuilt_alg, prebuilt_gen]

    return result, prebuild_result


def _gen_prebuild_hash(x90_file: Path, mp_payload: MpCommonArgs):
    """
    Calculate the prebuild hash for this x90 file, based on all the things which should trigger reprocessing.

    Changes which must trigger reprocessing of an x90 file:
     - x90 source:
     - kernel metadata used by the x90
     - transformation script
     - cli args

    """
    # We've analysed (a parsable version of) this x90.
    analysis_result = mp_payload.analysed_x90[x90_file]  # type: ignore

    # include the hashes of kernels used by this x90
    kernel_deps_hashes = {
        mp_payload.all_kernel_hashes[kernel_name] for kernel_name in analysis_result.kernel_deps}  # type: ignore

    # calculate the transformation script hash for this file
    transformation_script_hash = 0
    if mp_payload.transformation_script:
        transformation_script_return_path = mp_payload.transformation_script(x90_file, mp_payload.config)
        if transformation_script_return_path:
            transformation_script_hash = file_checksum(transformation_script_return_path).file_hash
    if transformation_script_hash == 0:
        warnings.warn('no transformation script specified')

    # hash everything which should trigger re-processing
    # todo: hash the psyclone version in case the built-in kernels change?
    prebuild_hash = sum([

        # the hash of the x90 (not of the parsable version, so includes invoke names)
        analysis_result.file_hash,

        # the hashes of the kernels used by this x90
        sum(kernel_deps_hashes),

        # the hash of the transformation script for this x90
        transformation_script_hash,

        # command-line arguments
        string_checksum(str(mp_payload.cli_args)),
    ])

    return prebuild_hash


def _get_prebuild_paths(prebuild_folder, modified_alg, psy_file, prebuild_hash):
    prebuilt_alg = Path(prebuild_folder / f'{modified_alg.stem}.{prebuild_hash}{modified_alg.suffix}')
    prebuilt_gen = Path(prebuild_folder / f'{psy_file.stem}.{prebuild_hash}{psy_file.suffix}')
    return prebuilt_alg, prebuilt_gen


def _check_override(check_path: Path, mp_payload: MpCommonArgs):
    """
    Delete the file if there's an override for it.

    Assumes `self.overrides_folder` is not None, and is a flat folder.

    Returns either the override or original path.

    """

    if check_path.name in mp_payload.override_files:
        # there is an override so delete this output file...
        logger.warning(f"\noverride found for '{check_path}'")
        check_path.unlink()
        # ... and return the override path instead
        return mp_payload.overrides_folder / check_path.name  # type: ignore

    # we didn't have an override, so continue using this file
    return check_path


# regex to convert an x90 into parsable fortran, so it can be analysed using a third party tool

WHITE = r'[\s&]+'
OPT_WHITE = r'[\s&]*'

SQ_STRING = "'[^']*'"
DQ_STRING = '"[^"]*"'
STRING = f'({SQ_STRING}|{DQ_STRING})'

NAME_KEYWORD = 'name' + OPT_WHITE + '=' + OPT_WHITE + STRING + OPT_WHITE + ',' + OPT_WHITE
NAMED_INVOKE = 'call' + WHITE + 'invoke' + OPT_WHITE + r'\(' + OPT_WHITE + NAME_KEYWORD

_x90_compliance_pattern = None


# todo: In the future, we'd like to extend fparser to handle the leading invoke keywords. (Lots of effort.)
def make_parsable_x90(x90_path: Path) -> Path:
    """
    Take out the leading name keyword in calls to invoke(), making temporary, parsable fortran from x90s.

    If present it looks like this::

        call invoke( name = "compute_dry_mass", ...

    Returns the path of the parsable file.

    This function is not slow so we're not creating prebuilds for this work.

    """
    global _x90_compliance_pattern
    if not _x90_compliance_pattern:
        _x90_compliance_pattern = re.compile(pattern=NAMED_INVOKE)

    # src = open(x90_path, 'rt').read()

    # Before we remove the name keywords to invoke, we must remove any comment lines.
    # This is the simplest way to avoid producing bad fortran when the name keyword is followed by a comment line.
    # I.e. The comment line doesn't have an "&", so we get "call invoke(!" with no "&", which is a syntax error.
    src_lines = open(x90_path, 'rt').readlines()
    no_comment_lines = [line for line in src_lines if not line.lstrip().startswith('!')]
    src = ''.join(no_comment_lines)

    replaced = []

    def repl(matchobj):
        # matchobj[0] contains the entire matching string, from "call" to the "," after the name keyword.
        # matchobj[1] contains the single group in the search pattern, which is defined in STRING.
        name = matchobj[1].replace('"', '').replace("'", "")
        replaced.append(name)
        return 'call invoke('

    out = _x90_compliance_pattern.sub(repl=repl, string=src)

    out_path = x90_path.with_suffix('.parsable_x90')
    open(out_path, 'wt').write(out)

    logger.debug(f'names removed from {str(x90_path)}: {replaced}')

    return out_path

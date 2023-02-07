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
from typing import Dict, List, Tuple, Optional, Set

from fab.tools import run_command

from fab import FabException

from fab.artefacts import SuffixFilter
from fab.parse.fortran import FortranAnalyser, AnalysedFortran
from fab.parse.x90 import X90Analyser, AnalysedX90
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath, file_checksum, file_walk, TimerLogger, \
    string_checksum, suffix_filter, by_type, log_or_dot_finish

logger = logging.getLogger(__name__)


# todo: should this be part of the psyclone step?
def psyclone_preprocessor(set_um_physics=False):
    um_physics = ['-DUM_PHYSICS'] if set_um_physics else []

    return PreProcessor(
        # todo: use env vars and param
        preprocessor='cpp -traditional-cpp',

        # todo: the input files changed to upper X90 at some point - handle both
        source=SuffixFilter('all_source', '.x90'),
        output_collection='preprocessed_x90',

        output_suffix='.x90',
        name='preprocess x90',
        common_flags=[
            '-P',
            '-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DCOUPLED',
            *um_physics,
        ],
    )


@dataclass
class MpPayload:
    """
    Runtime data for child processes to read.

    Contains data used to calculate the prebuild hash.

    """
    transformation_script_hash: int = 0
    # these optionals aren't really optional, that's just for the constructor
    analysed_x90: Optional[Dict[Path, AnalysedX90]] = None
    used_kernel_hashes: Optional[Dict[str, int]] = None
    removed_invoke_names: Optional[Dict[Path, List[str]]] = None


class Psyclone(Step):
    """

    """
    def __init__(self, name=None, kernel_roots=None,
                 transformation_script: Optional[Path] = None,
                 cli_args: Optional[List[str]] = None):
        super().__init__(name=name or 'psyclone')
        self.kernel_roots = kernel_roots or []
        self.transformation_script = transformation_script

        # "the gross switch which turns off MPI usage is a command-line argument"
        self.cli_args: List[str] = cli_args or []

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)
        x90s = artefact_store['preprocessed_x90']

        # get the data which child processes use to calculate prebuild hashes
        mp_payload = self.analysis_for_prebuilds(artefact_store)

        # the argument to run_mp contains, for each file, the filename and the mp payload.
        mp_arg = [(x90, mp_payload) for x90 in x90s]

        # run psyclone.
        with TimerLogger(f"running psyclone on {len(x90s)} x90 files"):
            results = self.run_mp(mp_arg, self.do_one_file)
        log_or_dot_finish(logger)
        # for every file, we get back a list of its output files plus a list of the prebuild copies.
        outputs, prebuilds = zip(*results)
        check_for_errors(outputs, caller_label=self.name)

        # flatten the list of lists we got back from run_mp
        output_files: List[Path] = list(chain(*by_type(outputs, List)))
        prebuild_files: List[Path] = list(chain(*by_type(prebuilds, List)))

        # record the output files in the artefact store for further processing
        artefact_store['psyclone_output'] = output_files
        outputs_str = "\n".join(map(str, output_files))
        logger.debug(f'psyclone outputs:\n{outputs_str}\n')

        # mark the prebuild files as being current so the cleanup step doesn't delete them
        config.add_current_prebuilds(prebuild_files)
        prebuilds_str = "\n".join(map(str, prebuild_files))
        logger.debug(f'psyclone prebuilds:\n{prebuilds_str}\n')

        # todo: delete any psy layer files which have hand-written overrides, in a given overrides folder
        # is this called psykal?
        # assert False

    # todo: test that we can run this step before or after the analysis step
    def analysis_for_prebuilds(self, artefact_store) -> MpPayload:
        """
        Analysis for PSyclone prebuilds.

        In order to build reusable psyclone results, we need to know everything that goes into making one.
        Then we can hash it all, and check for changes in subsequent builds.
        We'll build up this data in a payload object, to be passed to the child processes.

        Changes which must trigger reprocessing of an x90 file:
         - x90 source, comprising:
           - the parsable version of the source, with any invoke name keywords removed
           - any removed invoke name keywords
         - kernel metadata used by the x90
         - transformation script
         - cli args

        Later:
         - psyclone version, to cover changes to built-in kernels

        Kernels:

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

        The Psyclone step and the Analyse step:
        Both steps use the generic Fortran analyser, which recognises Psyclone kernel metadata.
        Analysis results are saved and reused. It doesn't matter which step is first.

        """
        mp_payload = MpPayload()

        # hash the transformation script
        if self.transformation_script:
            mp_payload.transformation_script_hash = file_checksum(self.transformation_script).file_hash
        else:
            warnings.warn('no transformation script specified')


        # Convert all the x90s to parsable fortran so they can be analysed.
        # For each file, we get back the fpath of the temporary, parsable file plus any removed invoke() names.
        # These names are part of our change detection.
        # Note: We could use the hash of the original x90 instead of capturing the removed names...
        x90s = artefact_store['preprocessed_x90']
        with TimerLogger(f"converting {len(x90s)} x90s into parsable fortran"):
            mp_results = self.run_mp(items=x90s, func=make_parsable_x90)

        # gather the paths of the parsable x90s we just created
        parsable_x90: Set[Path] = {p for p, _ in mp_results}

        # gather the name keywords which were removed from the x90s
        mp_payload.removed_invoke_names = {path.with_suffix('.x90'): names for path, names in mp_results}

        # Analyse the parsable x90s to see which kernels they use.
        # Each x90 analysis result contains the kernels they depend on.
        mp_payload.analysed_x90 = self._analyse_x90s(parsable_x90)
        used_kernels = set(chain.from_iterable(x90.kernel_deps for x90 in mp_payload.analysed_x90.values()))
        logger.info(f'found {len(used_kernels)} kernels used')

        # Analyse *all* the kernel files, hashing the psyclone kernel metadata.
        # We only need the hashes right now but they all need analysing anyway, and we don't want to parse twice,
        # so we pass them through the general fortran analyser, which currently recognises kernel metadata.
        # todo: We'd like to separate that from the general fortran analyser at some point, to reduce coupling.
        all_kernel_files = set(*chain(file_walk(root) for root in self.kernel_roots))
        all_kernel_f90 = suffix_filter(all_kernel_files, ['.f90'])
        all_kernel_hashes = self._analyse_kernels(all_kernel_f90)

        # we only need to remember the hashes of kernels which are used by our x90s
        mp_payload.used_kernel_hashes = _get_used_kernel_hashes(all_kernel_hashes, used_kernels)

        return mp_payload

    def _analyse_x90s(self, parsable_x90: Set[Path]) -> Dict[Path, AnalysedX90]:
        # Analyse the parsable version of the x90, finding kernel dependencies.
        x90_analyser = X90Analyser()
        x90_analyser._config = self._config

        with TimerLogger(f"analysing {len(parsable_x90)} parsable x90 files"):
            x90_results = self.run_mp(items=parsable_x90, func=x90_analyser.run)
        log_or_dot_finish(logger)
        x90_analyses, x90_artefacts = zip(*x90_results) if x90_results else (tuple(), tuple())
        check_for_errors(results=x90_analyses)

        # mark the analysis results files (i.e. prebuilds) as being current, so the cleanup knows not to delete them
        prebuild_files = list(by_type(x90_artefacts, Path))
        self._config.add_current_prebuilds(prebuild_files)

        # record the analysis result against the original x90 filename (not the parsable version we analysed)
        analysed_x90 = by_type(x90_analyses, AnalysedX90)
        return {result.fpath.with_suffix('.x90'): result for result in analysed_x90}

    def _analyse_kernels(self, kernel_files) -> Dict[str, int]:
        # We want to hash the kernel metadata (type defs).
        # We use the normal Fortran analyser, which records psyclone kernel metadata.
        # todo: We'd like to separate that from the general fortran analyser at some point, to reduce coupling.
        # The Analyse step also uses the same fortran analyser. It stores its results so they won't be analysed twice.
        fortran_analyser = FortranAnalyser()
        fortran_analyser._config = self._config
        with TimerLogger(f"analysing {len(kernel_files)} potential psyclone kernel files"):
            fortran_results = self.run_mp(items=kernel_files, func=fortran_analyser.run)
        log_or_dot_finish(logger)
        fortran_analyses, fortran_artefacts = zip(*fortran_results) if fortran_results else (tuple(), tuple())

        # mark the analysis results files (i.e. prebuilds) as being current, so the cleanup knows not to delete them
        prebuild_files = list(by_type(fortran_artefacts, Path))
        self._config.add_current_prebuilds(prebuild_files)

        errors: List[Exception] = list(by_type(fortran_analyses, Exception))
        if errors:
            errs_str = '\n\n'.join(map(str, errors))
            logger.error(f"There were {len(errors)} errors while parsing kernels:\n\n{errs_str}")

        analysed_fortran: List[AnalysedFortran] = list(by_type(fortran_analyses, AnalysedFortran))

        # gather all kernel hashes into one big lump
        all_kernel_hashes: Dict[str, int] = {}
        for af in analysed_fortran:
            assert set(af.psyclone_kernels).isdisjoint(all_kernel_hashes), \
                f"duplicate kernel name(s): {set(af.psyclone_kernels) & set(all_kernel_hashes)}"
            all_kernel_hashes.update(af.psyclone_kernels)

        return all_kernel_hashes

    def do_one_file(self, arg):
        x90_file, mp_payload = arg
        prebuild_hash = self._gen_prebuild_hash(x90_file, mp_payload)

        # These are the filenames we expect to be output for this x90 input file.
        # There will always be one modified_alg, and 0+ generated.
        modified_alg = x90_file.with_suffix('.f90')
        modified_alg = input_to_output_fpath(config=self._config, input_path=modified_alg)
        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')
        generated = input_to_output_fpath(config=self._config, input_path=generated)

        generated.parent.mkdir(parents=True, exist_ok=True)

        # todo: do we have handwritten overrides?

        # do we already have prebuilt results for this x90 file?
        prebuilt_alg, prebuilt_gen = self._get_prebuild_paths(modified_alg, generated, prebuild_hash)
        if prebuilt_alg.exists():
            # todo: error handling in here
            msg = f'found prebuilds for {x90_file}:\n    {prebuilt_alg}'
            shutil.copy2(prebuilt_alg, modified_alg)
            if prebuilt_gen.exists():
                msg += f'\n    {prebuilt_gen}'
                shutil.copy2(prebuilt_gen, generated)
            log_or_dot(logger=logger, msg=msg)

        else:
            try:
                # logger.info(f'running psyclone on {x90_file}')
                self.run_psyclone(generated, modified_alg, x90_file)

                shutil.copy2(modified_alg, prebuilt_alg)
                msg = f'created prebuilds for {x90_file}:\n    {prebuilt_alg}'
                if Path(generated).exists():
                    msg += f'\n    {prebuilt_gen}'
                    shutil.copy2(generated, prebuilt_gen)
                log_or_dot(logger=logger, msg=msg)

            except Exception as err:
                logger.error(err)
                return err, None

        # return the output files from psyclone
        result: List[Path] = [modified_alg]
        if Path(generated).exists():
            result.append(generated)

        # we also want to return the prebuild artefact files we created,
        # which are just copies, in the prebuild folder, with hashes in the filenames.
        prebuild_result: List[Path] = [prebuilt_alg, prebuilt_gen]

        return result, prebuild_result

    def _gen_prebuild_hash(self, x90_file: Path, mp_payload: MpPayload):
        """
        Calculate the prebuild hash for this x90 file, based on all the things which should trigger reprocessing.

        """
        # We've analysed (a parsable version of) this x90.
        analysis_result = mp_payload.analysed_x90[x90_file]

        # include the list of invoke names that were removed from this x90 before fortran analysis
        # (alternatively, we could use the hash of the non-parsable x90 and not record removed names...)
        # todo: chat about that sometime
        removed_inkove_names = mp_payload.removed_invoke_names.get(x90_file)
        if removed_inkove_names is None:
            raise FabException(f"No removed name data for path '{x90_file}'")

        # include the hashes of kernels used by this x90
        kernel_deps_hashes = {mp_payload.used_kernel_hashes[kernel_name] for kernel_name in analysis_result.kernel_deps}

        # hash everything which should trigger re-processing
        # todo: hash the psyclone version in case the built-in kernels change?
        prebuild_hash = sum([

            # the parsable version of the x90
            analysis_result.file_hash,

            # the 'name=' keywords passed to invoke(), which were removed from the x90 to make it parsable
            string_checksum(str(removed_inkove_names)),

            # the hashes of the kernels used by this x90
            sum(kernel_deps_hashes),

            #
            mp_payload.transformation_script_hash,

            # command-line arguments
            string_checksum(str(self.cli_args)),
        ])

        return prebuild_hash

    def _get_prebuild_paths(self, modified_alg, generated, prebuild_hash):
        prebuilt_alg = Path(self._config.prebuild_folder / f'{modified_alg.stem}.{prebuild_hash}{modified_alg.suffix}')
        prebuilt_gen = Path(self._config.prebuild_folder / f'{generated.stem}.{prebuild_hash}{generated.suffix}')
        return prebuilt_alg, prebuilt_gen

    def run_psyclone(self, generated, modified_alg, x90_file):

        # -d specifies "a root directory structure containing kernel source"
        kernel_args = sum([['-d', k] for k in self.kernel_roots], [])

        # transformation python script
        transform_options = ['-s', self.transformation_script] if self.transformation_script else []

        command = [
            'psyclone', '-api', 'dynamo0.3',
            '-l', 'all',
            *kernel_args,
            '-opsy', generated,  # filename of generated PSy code
            '-oalg', modified_alg,  # filename of transformed algorithm code
            *transform_options,
            *self.cli_args,
            x90_file,
        ]

        run_command(command)


# regex to convert an x90 into parsable fortran, so it can be analysed using a third party tool

WHITE = r'[\s&]+'
OPT_WHITE = r'[\s&]*'

SQ_STRING = "'[^']*'"
DQ_STRING = '"[^"]*"'
STRING = f'({SQ_STRING}|{DQ_STRING})'

NAME_KEYWORD = 'name' + OPT_WHITE + '=' + OPT_WHITE + STRING + OPT_WHITE + ',' + OPT_WHITE
NAMED_INVOKE = 'call' + WHITE + 'invoke' + OPT_WHITE + r'\(' + OPT_WHITE + NAME_KEYWORD

_x90_compliance_pattern = None


def make_parsable_x90(x90_path: Path) -> Tuple[Path, List[str]]:
    """
    Take out the leading name keyword in calls to invoke(), making temporary, parsable fortran from x90s.

    If present it looks like this::

        call invoke( name = "compute_dry_mass", ...

    Returns the path of the parsable file, plus any invoke() names which were removed.

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

    return out_path, replaced


def _get_used_kernel_hashes(all_kernel_hashes: Dict[str, int], used_kernels: Set) -> Dict[str, int]:

    used_kernel_hashes = {}
    for kernel in used_kernels:
        kernal_hash = all_kernel_hashes.get(kernel)
        if not kernal_hash:
            # If we can't get a hash for this kernel, we can't tell if it's changed.
            # We *could* continue, without prebuilds, but psyclone would presumably fail with a missing kernel.
            raise FabException(f"could not find hash for used kernel '{kernel}'")
        used_kernel_hashes[kernel] = kernal_hash

    return used_kernel_hashes

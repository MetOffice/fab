# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A preprocessor and code generation step for PSyclone.
https://github.com/stfc/PSyclone

"""
import logging
import re
import shutil
import warnings
from itertools import chain
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Iterable, Set

from fab import FabException
from fparser.two.Fortran2003 import Use_Stmt

from fab.artefacts import SuffixFilter
from fab.parse.fortran.fortran import FortranAnalyser, AnalysedFortran
from fab.parse.fortran.x90 import X90Analyser, AnalysedX90
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath, run_command, file_checksum, file_walk, TimerLogger, \
    string_checksum, suffix_filter

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


class Psyclone(Step):
    """

    .. note::

        This step must run before the Analyse step because it performs extra processing on kernel files.
        Fab's Fortran analysis uses prebuilds if available, so
        xxx


    """
    def __init__(self, name=None, kernel_roots=None,
                 transformation_script: Optional[Path] = None,
                 cli_args: Optional[List[str]] = None):
        super().__init__(name=name or 'psyclone')
        self.kernel_roots = kernel_roots or []
        self.transformation_script = transformation_script

        # "the gross switch which turns off MPI usage is a command-line argument"
        self.cli_args: List[str] = cli_args or []

        # runtime, for child processes to read
        self._transformation_script_hash = None
        self._file_hashes = None
        self._analysed_x90: Dict[Path, AnalysedX90] = {}  # analysis of fortran-compliant versions of the x90s
        self._used_kernel_hashes: Dict[str: int] = {}  # hash of every kernel used by the x90
        self._removed_invoke_names: Dict[Path, List[str]] = {}  # name keywords passed to invoke, removed for parsing

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)

        # In order to build reusable psyclone results, we need to know everything that goes into making one.
        # Then we can hash it all, and check for changes in subsequent builds.

        # Analyse all the x90s, and the kernels (and other x90s) they use.
        # Hash the dependencies for every x90.
        #
        # We should be able to analyse just the x90s and the kernel root folders.
        # The configs we've seen set the entire source root as the kernel root, but that's ok.
        # Depending on the kernel_roots config, we might analyse the whole codebase
        # which is fine because we're going to have to analyse it anyway later in the build.
        #
        # We don't need all the analysis step features,
        # like mo-commented deps, unreferenced deps and dependency tree building.
        # We just need to parse the x90s and the kernel files, and produce a symbol table for finding module source.
        #

        self.analyse(artefact_store)

        # hash the trees
        # in the fortran compiler we hash the module files themselves
        # but they're not built yet in this step so we'll hash the fortran files which define the module dependencies.

        # what's the transformation script? we need to hash that.
        # (can be omitted, but warn)
        # todo: what about anything the transformation script might import?
        if self.transformation_script:
            self._transformation_script_hash = file_checksum(self.transformation_script).file_hash
        else:
            warnings.warn('no transformation script specified')
            self._transformation_script_hash = 0

        results = self.run_mp(artefact_store['preprocessed_x90'], self.do_one_file)
        check_for_errors(results, caller_label=self.name)

        # delete any psy layer files which have hand-written overrides
        # is this called psykal?
        assert False

        successes = list(filter(lambda r: not isinstance(r, Exception), results))
        logger.info(f"success with {len(successes)} files")
        artefact_store['psyclone_output'] = []
        for files in successes:
            artefact_store['psyclone_output'].extend(files)

    # todo: test that we can run this step before or after the analysis step
    def analyse(self, artefact_store):
        """
        Analysis for PSyclone prebuilds.

        Changes which trigger reprocessing of an x90 file:
         - x90 source, comprising:
           - the parsable, fortran-compliant source with any invoke names removed
           - any removed invoke names
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
        `PSyclone built-ins <https://github.com/stfc/PSyclone/blob/ebb7f1aa32a9377da6ccc1ec04eec4adbc1e0a0a/src/psyclone/domain/lfric/lfric_builtins.py#L2136>`_.
        They will not appear in use statements and can be ignored.

        The Psyclone step and the Analyse step:
        Both steps use the generic Fortran analyser, which recognises Psyclone kernel metadata.
        Analysis results are saved and reused. It doesn't matter which step is first.

        """

        # Convert all the x90s to compliant fortran so they can be analysed.
        # For each file, we get back the fpath of the temporary, compliant file plus any removed invoke() names.
        # These names are part of our change detection.
        # Note: We could use the hash of the pre-compliant x90 instead of capturing the removed names...
        mp_results = self.run_mp(items=artefact_store['preprocessed_x90'], func=make_compliant_x90)
        self._removed_invoke_names: Dict[Path, List[str]] = dict(mp_results)
        compliant_x90: Set[Path] = set(self._removed_invoke_names.keys())

        # Analyse the compliant x90s to see which kernels they use.
        self._analysed_x90 = self._analyse_x90s(compliant_x90)
        # each x90 analysis result contains the kernels they depend on, and the names of the modules they're in
        # todo: we'd simplify this code if the x90 analyser didn't record the modules they're in
        kernel_sets = [set(a.kernel_deps.keys()) for a in self._analysed_x90.values()]
        used_kernels = set.union(*kernel_sets)

        # Analyse *all* the kernel files, hashing the psyclone kernel metadata.
        # We only need the hashes right now but they all need analysing anyway, and we don't want to parse twice,
        # so we pass them through the general fortran analyser, which currently recognises kernel metadata.
        # todo: We'd like to separate that from the general fortran analyser at some point, to reduce coupling.
        all_kernel_files = set(*chain(file_walk(root) for root in self.kernel_roots))
        all_kernel_f90 = suffix_filter(all_kernel_files, ['.f90'])
        all_kernel_hashes = self._analyse_kernels(all_kernel_f90)

        # we only need to remember the hashes of kernels which are used by our x90s
        self._used_kernel_hashes = {}
        for kernel in used_kernels:
            self._used_kernel_hashes[kernel] = all_kernel_hashes.get(kernel)
            if not self._used_kernel_hashes[kernel]:
                # If we can't get a hash for this kernel, we can't tell if it's changed.
                # We *could* continue, without prebuilds, but psyclone would presumably fail with a missing kernel.
                raise FabException(f"could not find hash for used kernel '{kernel}'")

    def _analyse_x90s(self, compliant_x90: Set[Path]) -> Dict[Path, AnalysedX90]:
        # Parse fortran compliant x90, finding kernel dependencies.
        x90_analyser = X90Analyser()
        x90_analyser._prebuild_folder = self._config.prebuild_folder
        with TimerLogger(f"analysing {len(compliant_x90)} fortran compliant x90 files"):
            results = self.run_mp(items=compliant_x90, func=x90_analyser.run)

        # record the analysis result against the original x90 filename
        return {result.fpath.with_suffix('.x90'): result for result in results}

        # todo: error handling

    def _analyse_kernels(self, kernel_files) -> Dict[str, int]:
        # We want to hash the kernel metadata (type defs).
        # We use the normal Fortran analyser, which records psyclone kernel metadata.
        # todo: We'd like to separate that from the general fortran analyser at some point, to reduce coupling.
        # The Analyse step also uses the same fortran analyser. It stores its results so they won't be analysed twice.
        fortran_analyser = FortranAnalyser()
        fortran_analyser._prebuild_folder = self._config.prebuild_folder
        with TimerLogger(f"analysing {len(kernel_files)} psyclone kernel files"):
            analysed_fortran: List[AnalysedFortran] = self.run_mp(items=kernel_files, func=fortran_analyser.run)

        # gather all kernel hashes into one big lump
        all_kernel_hashes: Dict[str, int] = {}
        for af in analysed_fortran:
            assert set(af.psyclone_kernels).isdisjoint(all_kernel_hashes), \
                f"duplicate kernel name(s): {set(af.psyclone_kernels) & set(all_kernel_hashes)}"
            all_kernel_hashes |= af.psyclone_kernels

        return all_kernel_hashes

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))

        # We've analysed this x90.
        # Note: This analysis result is for a fortran-compliant version of the original x90.
        #       We gave it a different suffix, '.compliant_x90'.
        analysis_result = self._analysed_x90[x90_file]

        # we'll hash the list of invoke names that were removed before fortran analysis
        removed_inkove_names = self._removed_invoke_names.get(x90_file)
        if removed_inkove_names is None:
            raise FabException(f"Path not found in 'removed invoke names': '{x90_file}'")

        # we'll include the hashes of kernel dependencies
        kernel_deps_hashes = {self._used_kernel_hashes[kernel_name] for kernel_name in analysis_result.kernel_deps}

        # hash everything which should trigger re-processing
        # todo: hash the psyclone version in case the built-in kernels change?
        prebuild_hash = sum([

            # the fortran compliant version of the x90
            analysis_result.file_hash,

            # the 'name=' keywords passed to invoke(), which were removed from the x90 to make it compliant
            string_checksum(str(removed_inkove_names)),

            # the hashes of the kernels used by this x90
            sum(kernel_deps_hashes),

            #
            self._transformation_script_hash,

            # command-line arguments
            string_checksum(str(self.cli_args)),
        ])

        # These are the filenames we expect to be output for this x90 input file.
        # There will always be one modified_alg, and 0+ generated.
        modified_alg = x90_file.with_suffix('.f90')
        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')

        # generate into the build output, not the source
        generated = input_to_output_fpath(config=self._config, input_path=generated)
        modified_alg = input_to_output_fpath(config=self._config, input_path=modified_alg)
        generated.parent.mkdir(parents=True, exist_ok=True)

        # todo: do we have handwritten overrides

        # do we already have prebuilt results for this x90 file?
        prebuilt_alg, prebuilt_gen = self._get_prebuild_paths(modified_alg, generated, prebuild_hash)
        if prebuilt_alg.exists():
            logger.info(f'prebuild(s) found for {x90_file}')
            shutil.copy2(prebuilt_alg, modified_alg)
            if prebuilt_gen.exists():
                shutil.copy2(prebuilt_gen, generated)

        else:
            try:
                self.run_psyclone(generated, modified_alg, x90_file)
            except Exception as err:
                logger.error(err)
                return err

        result = [modified_alg]
        if Path(generated).exists():
            result.append(generated)
        return result

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

    def _get_prebuild_paths(self, modified_alg, generated, prebuild_hash):
        prebuilt_alg = Path(self._config.prebuild_folder / f'{modified_alg.stem}.{prebuild_hash}.{modified_alg.suffix}')
        prebuilt_gen = Path(self._config.prebuild_folder / f'{generated.stem}.{prebuild_hash}.{prebuild_hash.suffix}')
        return prebuilt_alg, prebuilt_gen


# regex to convert an x90 into a fortran-compliant file, so it can be parsed with a third party tool

WHITE = r'[\s&]+'
OPT_WHITE = r'[\s&]*'

SQ_STRING = "'[^']*'"
DQ_STRING = '"[^"]*"'
STRING = f'({SQ_STRING}|{DQ_STRING})'

NAME_KEYWORD = 'name' + OPT_WHITE + '=' + OPT_WHITE + STRING + OPT_WHITE + ',' + OPT_WHITE
NAMED_INVOKE = 'call' + WHITE + 'invoke' + OPT_WHITE + r'\(' + OPT_WHITE + NAME_KEYWORD

_x90_compliance_pattern = None


def make_compliant_x90(x90_path: Path) -> Tuple[Path, List[str]]:
    """
    Take out the leading name keyword in calls to invoke(), making temporary, parsable fortran from x90s.

    If present it looks like this::

        call invoke( name = "compute_dry_mass", ...

    Returns the path of the Fortran compliant file, plus any invoke() names which were removed.

    """
    global _x90_compliance_pattern
    if not _x90_compliance_pattern:
        _x90_compliance_pattern = re.compile(pattern=NAMED_INVOKE)

    src = open(x90_path, 'rt').read()
    replaced = []

    def repl(matchobj):
        # matchobj[0] contains the entire matching string, from "call" to the "," after the name keyword.
        # matchobj[1] contains the single group in the search pattern, which is defined in STRING.
        name = matchobj[1].replace('"', '').replace("'", "")
        replaced.append(name)
        return 'call invoke('

    out = _x90_compliance_pattern.sub(repl=repl, string=src)

    out_path = x90_path.with_suffix('.compliant_x90')
    open(out_path, 'wt').write(out)

    return out_path, replaced

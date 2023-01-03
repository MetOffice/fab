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
import warnings
from itertools import chain
from pathlib import Path
from typing import Dict, List, Tuple

from fparser.two.Fortran2003 import Use_Stmt

from fab.artefacts import SuffixFilter
from fab.parse.fortran.fortran import FortranAnalyser
from fab.parse.fortran.x90 import X90Analyser
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath, run_command, file_checksum, file_walk, TimerLogger

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
    def __init__(self, name=None, kernel_roots=None, transformation_script=None, cli_args=None):
        super().__init__(name=name or 'psyclone')
        self.kernel_roots = kernel_roots or []
        self.transformation_script = transformation_script
        self.cli_args = cli_args or []

        # runtime
        self._transformation_script_hash = None
        self._file_hashes = None
        self._used_kernel_hashes = None

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

        Changes which cause a rebuild:
         - x90
         - kernel metadata used by the x90
         - transformation script
         - cli args

        Later:
         - psyclone version, to cover changes to built-in kernels
         - kernel metadata type defs within the kernel file, not the whole kernel file

        Kernels:
        Kernel metadata are the type definitions passed to invoke().
        For now we detect changed kernel metadata by looking for changes to their source file.
        We plan to upgrade this, detecting change to the kernel metadata within the file.

        For example this x90 code depends on the kernel `compute_total_mass_kernel_type`.
        .. code-block:: fortran

            call invoke( name = "compute_dry_mass",                                         &
                         compute_total_mass_kernel_type(dry_mass, rho, chi, panel_id, qr),  &
                         sum_X(total_dry, dry_mass))

        We can locate the metadata source for this kernel by looking in the use statements at the top of the x90.
        .. code-block:: fortran

            use compute_total_mass_kernel_mod,   only: compute_total_mass_kernel_type

        Some kernels, such as `setval_c`, are PSyclone `built-ins <https://github.com/stfc/PSyclone/blob/ebb7f1aa32a9377da6ccc1ec04eec4adbc1e0a0a/src/psyclone/domain/lfric/lfric_builtins.py#L2136>`_.
        They will not appear in use statements and can be ignored,
        although the PSyclone version should be included in the hash in case they change.

        The Psyclone and the Analyse steps:
        If we want the flexibility to run the Analyse step either before or after this step,
        then we need to analyse the t90 output from this step in here.

        Further work finer-grained kernel detection:
        To detect finer-grained changes in the kernel metadata; the type def not the whole file,
        we'll need to run the kernel file through the fparser and find the type defs.
        We don't want to run it through fparser twice (the Analyse step also does this)
        so we'll need to design a solution which knows it's dealing with a kernel file,
        and runs different or  extra node tree analyis for kernel files.

        """

        # Convert all the x90s to compliant fortran so they can be analysed.
        # For each file, we get back the fpath of the temporary, compliant file plus any removed invoke() names.
        # These names are part of our change detection.
        # Note: we could use the hash of the pre-compliant x90 instead of capturing the removed names...
        mp_results = self.run_mp(items=artefact_store['preprocessed_x90'], func=make_compliant_x90)
        compliant_x90: Dict[Path, List[str]] = dict(mp_results)

        # Analyse the compliant x90s to see which kernels they use.
        analysed_x90 = self._analyse_x90s(compliant_x90)
        used_kernels = set(chain(a.kernel_deps for a in analysed_x90))

        # Hash every used kernel (metadata, a type definition).
        # Analyse *all* kernel files to find them.
        # We only need their hashes right now, but they all need analysing anyway.
        all_kernel_files = set(chain(file_walk(root) for root in self.kernel_roots))
        self._kernel_hashes = self._analyse_kernels(all_kernel_files, used_kernels)

        # {x90: <list of kernels>}
        x90_kernels: Dict[str, List[str]] = self._analyse_x90s(compliant_x90)
        all_used_kernels = set(chain(x90_kernels.values()))

        # Analyse the kernel files, looking for the kernels we use.
        # Get back a hash for every kernel, taken from the type definition source.
        # {kernel: hash}
        # kernel_hashes = self._analyse_kernels(kernel_files, all_used_kernels)

    def _analyse_x90s(self, compliant_x90):
        # Parse fortran compliant x90, finding kernel dependencies.
        x90_analyser = X90Analyser()
        x90_analyser._prebuild_folder = self._config.prebuild_folder
        with TimerLogger(f"analysing {len(compliant_x90)} fortran compliant x90 files"):
            analysed_x90 = self.run_mp(items=compliant_x90, func=x90_analyser.run)
        return analysed_x90

    def _analyse_kernels(self, kernel_files, used_kernels):
        # We want to hash the kernel metadata, which are type defs.
        # We use the normal Fortran analyser and inject our own kernel handler.
        # The Analyse step also uses the fortran analyser. It stores its results so they won't be analysed twice.
        # todo: What if the analyser ran first? We won't walk the nodes!
        # todo: what if the analyser ran last time...we need to store the kernel hashs like prebuilds...?...

        # we need to be able to get kernel hashes even if the file has been analysed.
        # so there's no point injecting our kernel handler into the normal analyser.
        #
        # might be best to just re-parse, or save the parse tree?
        #
        # or just have the foretran analyser *always* record kernel defs?
        #
        # that's it.
        #
        #
        #

        # used_kernel_hashes = {}

        fortran_analyser = FortranAnalyser()
        fortran_analyser._prebuild_folder = self._config.prebuild_folder
        with TimerLogger(f"analysing {len(kernel_files)} kernel files"):
            fortran_results = self.run_mp(items=kernel_files, func=fortran_analyser.run)

        return used_kernel_hashes

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))


        # can we reuse previous build artefacts?
        analysis_result = self._analysed_x90[x90_file]
        # todo: don't just silently use 0 for a missing dep hash
        # mod_deps_hashes = {mod_dep: self._mod_hashes.get(mod_dep, 0) for mod_dep in analysis_result.module_deps}
        kernel_deps_hashes = {file_dep: self._kernel_hashes.get(kernel_dep, 0) for kernel_dep in analysis_result.kernel_deps}

        # we want the hash of every fortran file which defines a module on which we depend.
        # the symbol table maps modules to files.


        # todo: hash the list of invoke names that were removed for fortran analysis


        prebuild_hash = sum([
            analysis_result.file_hash,
            sum(kernel_deps_hashes.values()),
            self._transformation_script_hash,
        ])



        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')
        modified_alg = x90_file.with_suffix('.f90')

        # generate into the build output, not the source
        generated = input_to_output_fpath(config=self._config, input_path=generated)
        modified_alg = input_to_output_fpath(config=self._config, input_path=modified_alg)
        generated.parent.mkdir(parents=True, exist_ok=True)

        # -d specifies "a root directory structure containing kernel source"
        kernel_options = sum([['-d', k] for k in self.kernel_roots], [])

        # transformation python script
        transform_options = ['-s', self.transformation_script] if self.transformation_script else []

        # todo: do we allow command line arguments to be passed through?
        #       if so, we need to hash those as well
        #       "the gross switch which turns off MPI usage is a command-line argument"

        # todo: has the psyclone version in case the built-in kernels change?

        command = [
            'psyclone', '-api', 'dynamo0.3',
            '-l', 'all',
            *kernel_options,
            '-opsy', generated,  # filename of generated PSy code
            '-oalg', modified_alg,  # filename of transformed algorithm code
            *transform_options,
            *self.cli_args,
            x90_file,
        ]

        if self._config.reuse_artefacts and Path(modified_alg).exists():
            pass
        else:
            try:
                run_command(command)
            except Exception as err:
                logger.error(err)
                return err

        result = [modified_alg]
        if Path(generated).exists():
            result.append(generated)
        return result


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

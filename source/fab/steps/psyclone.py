# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
A preprocessor and code generation step for PSyclone.
https://github.com/stfc/PSyclone

"""
from pathlib import Path
from typing import Dict, Iterable, List

from fab.dep_tree import AnalysedFile
from fab.steps.analyse import _analyse_dependencies

from fab.tasks.fortran import FortranAnalyser

from fab.artefacts import SuffixFilter
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath, run_command, by_type, TimerLogger
from run_configs.lfric.lfric_common import logger


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

    def __init__(self, name=None, kernel_roots=None):
        super().__init__(name=name or 'psyclone')
        self.kernel_roots = kernel_roots or []

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)

        # In order to build reusable psyclone results, we need to know everything that goes into making one.
        # Then we can hash it all, and check for changes in subsequent builds.

        # Analyse all the x90s and the kernels (and other x90s) they use to get dependency trees.
        # Depending on the kernel_roots config, this might mean analysing the whole codebase,
        # which is fine because we're going to have to analyse it anyway later in the build.
        #
        # We don't need all the analysis step features, like mo-commented deps and unreferenced deps,
        # we just need to parsing and the dependency analysis.
        #
        # We should be able to analyse just the x90s and the kernel root folders.
        # The configs we've seen set the source root as the kernel root, but that's ok.

        self.analyse()

        # hash the trees
        # in the fortran compiler we hash the module files themselves
        # but they're not built yet in this step so we'll hash the fortran files which define the module dependencies.

        # what's the transformation script? we need to hash that.
        # (can be omitted, but warn)
        # todo: what about anything the transformation script might import?
        transformation_script = xxx
        transformation_script_hash = something(transformation_script)



        results = self.run_mp(artefact_store['preprocessed_x90'], self.do_one_file)
        check_for_errors(results, caller_label=self.name)

        # delete any psy layer files which have hand-written overrides
        # is this called psykal?
        xxx

        successes = list(filter(lambda r: not isinstance(r, Exception), results))
        logger.info(f"success with {len(successes)} files")
        artefact_store['psyclone_output'] = []
        for files in successes:
            artefact_store['psyclone_output'].extend(files)

    # todo: test that we can run this step before or after the analysis step
    def analyse(self):
        """
        A cut-down version of the analysis step, for incremental Psyclone, so we know when dependencies change.

        We don't need all the analysis step features, like mo-commented deps and unreferenced deps,
        we just need to parsing and the dependency analysis.

        """

        # convert all the x90s to compliant fortran so they can be analysed
        compliant_x90 = self.run_mp(items=x90, func=self._make_compliant)

        # analyse the compliant x90s and any kernels (or other x90s) they use
        # this uses the same parser as the analyser so we can reuse analysis results
        # todo: pass in the std
        fortran_analyser = FortranAnalyser()
        with TimerLogger(f"Psyclone: analysing {len(compliant_x90)} preprocessed fortran files"):
            analysis_results = self.run_mp(items=compliant_x90, func=fortran_analyser.run)

        # Check for parse errors but don't fail. The failed files might not be required.
        exceptions = list(by_type(analysis_results, Exception))
        if exceptions:
            logger.error(f"Psyclone: {len(exceptions)} analysis errors")

        analysed_files = set(by_type(analysis_results, AnalysedFile))

        # get a "build tree" for every x90
        project_source_tree, symbols = _analyse_dependencies(analysed_files)

        # extract the build trees needed for psyclone
        # we'll hash them to check for change, so we know when to re-run psyclone
        trees = set()
        for x90_root in compliant:
            extract_sub_tree(project_source_tree, symbols[x90_root])

    def _make_compliant(self, x90: Path) -> Path:
        """
        Take out the leading keyword in calls to invoke(), making temporary, parsable fortran from x90s.

        If present it looks like this::

            call invoke( name = "compute_dry_mass", ...

        """
        assert False

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))


        # can we reuse previous build artefacts?
        analysis_result = self.analysed_x90[x90_file]
        # todo: don't just silently use 0 for a missing dep hash
        mod_deps_hashes = {mod_dep: self._mod_hashes.get(mod_dep, 0) for mod_dep in analysis_result.module_deps}

        # we want the hash of every fortran file which defines a module on which we depend.
        # the symbol table maps modules to files.



        prebuild_hash = sum([
            analysis_result.file_hash,
            sum(mod_deps_hashes.values()),
            transformation_script_hash
        ])



        generated = x90_file.parent / (str(x90_file.stem) + '_psy.f90')
        modified_alg = x90_file.with_suffix('.f90')

        # generate into the build output, not the source
        generated = input_to_output_fpath(config=self._config, input_path=generated)
        modified_alg = input_to_output_fpath(config=self._config, input_path=modified_alg)
        generated.parent.mkdir(parents=True, exist_ok=True)

        # -d specifies "a root directory structure containing kernel source"
        kernel_options = sum([['-d', k] for k in self.kernel_roots], [])

        command = [
            'psyclone', '-api', 'dynamo0.3',
            '-l', 'all',
            *kernel_options,
            '-opsy', generated,  # filename of generated PSy code
            '-oalg', modified_alg,  # filename of transformed algorithm code
            '-s', transformation_script,  # transformation python script
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

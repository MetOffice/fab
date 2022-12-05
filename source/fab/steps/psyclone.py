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
from typing import Dict

from fab.artefacts import SuffixFilter
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath, run_command
from run_configs.lfric.lfric_common import logger


def psyclone_preprocessor(set_um_physics=False):
    um_physics = ['-DUM_PHYSICS'] if set_um_physics else []

    return PreProcessor(
        # todo: use env vars and param
        preprocessor='cpp -traditional-cpp',

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

        results = self.run_mp(artefact_store['preprocessed_x90'], self.do_one_file)
        check_for_errors(results, caller_label=self.name)

        successes = list(filter(lambda r: not isinstance(r, Exception), results))
        logger.info(f"success with {len(successes)} files")
        artefact_store['psyclone_output'] = []
        for files in successes:
            artefact_store['psyclone_output'].extend(files)

    def do_one_file(self, x90_file):
        log_or_dot(logger=logger, msg=str(x90_file))

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
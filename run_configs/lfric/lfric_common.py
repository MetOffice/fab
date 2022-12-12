import logging
import os
import shutil
from pathlib import Path
from typing import Dict

from fab.artefacts import SuffixFilter
from fab.steps import Step, check_for_errors
from fab.steps.preprocess import PreProcessor
from fab.util import log_or_dot, input_to_output_fpath
from fab.tools import run_command

logger = logging.getLogger('fab')


class Configurator(Step):

    def __init__(self, lfric_source: Path, gpl_utils_source: Path, rose_meta_conf: Path, config_dir=None):
        super().__init__(name='configurator thing')
        self.lfric_source = lfric_source
        self.gpl_utils_source = gpl_utils_source
        self.rose_meta_conf = rose_meta_conf
        self.config_dir = config_dir

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store=artefact_store, config=config)

        rose_picker_tool = self.gpl_utils_source / 'rose_picker/rose_picker'
        gen_namelist_tool = self.lfric_source / 'infrastructure/build/tools/GenerateNamelist'
        gen_loader_tool = self.lfric_source / 'infrastructure/build/tools/GenerateLoader'
        gen_feigns_tool = self.lfric_source / 'infrastructure/build/tools/GenerateFeigns'

        config_dir = self.config_dir or config.source_root / 'configuration'

        env = os.environ.copy()
        rose_lfric_path = self.gpl_utils_source / 'lib/python'
        env['PYTHONPATH'] += f':{rose_lfric_path}'

        # "rose picker"
        # creates rose-meta.json and config_namelists.txt in gungho/source/configuration
        logger.info('rose_picker')
        run_command(
            command=[
                str(rose_picker_tool), str(self.rose_meta_conf),
                '-directory', str(config_dir),
                '-include_dirs', self.lfric_source],
            env=env,
        )

        # "build_config_loaders"
        # builds a bunch of f90s from the json
        logger.info('GenerateNamelist')
        run_command(
            command=[
                str(gen_namelist_tool),
                '-verbose',
                str(config_dir / 'rose-meta.json'),
                '-directory', str(config_dir),
                # '--norandom_enums'
            ]
        )

        # create configuration_mod.f90 in source root
        logger.info('GenerateLoader')
        names = [name.strip() for name in open(config_dir / 'config_namelists.txt').readlines()]
        configuration_mod_fpath = config.source_root / 'configuration_mod.f90'
        run_command(
            command=[
                str(gen_loader_tool),
                configuration_mod_fpath,
                *names,
            ]
        )

        # create feign_config_mod.f90 in source root
        logger.info('GenerateFeigns')
        feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'
        run_command(
            command=[
                str(gen_feigns_tool),
                str(config_dir / 'rose-meta.json'),
                '-output', feign_config_mod_fpath,
            ]
        )

        # put the generated source into an artefact
        artefact_store['configurator_output'] = [
            configuration_mod_fpath,
            feign_config_mod_fpath
        ]


class FparserWorkaround_StopConcatenation(Step):
    """
    fparser can't handle string concat in a stop statement. This step is a workaround.

    https://github.com/stfc/fparser/issues/330

    """
    def run(self, artefact_store, config):
        feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'

        # rename "broken" version
        broken_version = feign_config_mod_fpath.with_suffix('.broken')
        shutil.move(feign_config_mod_fpath, broken_version)

        # make fixed version
        bad = "_config: '// &\n        'Unable to close temporary file'"
        good = "_config: Unable to close temporary file'"

        open(feign_config_mod_fpath, 'wt').write(
            open(broken_version, 'rt').read().replace(bad, good))


def psyclone_preprocessor(set_um_physics=False):
    um_physics = ['-DUM_PHYSICS'] if set_um_physics else []

    return PreProcessor(
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

import logging
import os
import shutil
from pathlib import Path
from typing import Dict

from fab.steps import Step
from fab.tools import run_command

logger = logging.getLogger('fab')


# todo: is this part of psyclone? if so, put  it in the psyclone step module?
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

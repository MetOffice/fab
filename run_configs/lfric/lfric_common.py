import logging
import os
import shutil
from pathlib import Path

from fab.steps import step
from fab.tools import run_command

logger = logging.getLogger('fab')


# todo: is this part of psyclone? if so, put  it in the psyclone step module?
@step
def configurator(config, lfric_source: Path, gpl_utils_source: Path, rose_meta_conf: Path, config_dir=None):

    rose_picker_tool = gpl_utils_source / 'rose_picker/rose_picker'
    gen_namelist_tool = lfric_source / 'infrastructure/build/tools/GenerateNamelist'
    gen_loader_tool = lfric_source / 'infrastructure/build/tools/GenerateLoader'
    gen_feigns_tool = lfric_source / 'infrastructure/build/tools/GenerateFeigns'

    config_dir = config_dir or config.source_root / 'configuration'

    env = os.environ.copy()
    rose_lfric_path = gpl_utils_source / 'lib/python'
    env['PYTHONPATH'] += f':{rose_lfric_path}'

    # "rose picker"
    # creates rose-meta.json and config_namelists.txt in gungho/source/configuration
    logger.info('rose_picker')
    run_command(
        command=[
            str(rose_picker_tool), str(rose_meta_conf),
            '-directory', str(config_dir),
            '-include_dirs', lfric_source],
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
    # todo: we shouldn't need to do this, should we?
    #       it's just going to be found in the source folder with everything else.
    config._artefact_store['configurator_output'] = [
        configuration_mod_fpath,
        feign_config_mod_fpath
    ]


@step
def fparser_workaround_stop_concatenation(config):
    """
    fparser can't handle string concat in a stop statement. This step is a workaround.

    https://github.com/stfc/fparser/issues/330

    """
    feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'

    # rename "broken" version
    broken_version = feign_config_mod_fpath.with_suffix('.broken')
    shutil.move(feign_config_mod_fpath, broken_version)

    # make fixed version
    bad = "_config: '// &\n        'Unable to close temporary file'"
    good = "_config: Unable to close temporary file'"

    open(feign_config_mod_fpath, 'wt').write(
        open(broken_version, 'rt').read().replace(bad, good))

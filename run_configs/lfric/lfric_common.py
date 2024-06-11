import logging
import os
import shutil
from pathlib import Path

from fab.steps import step
from fab.tools import Categories, Tool

logger = logging.getLogger('fab')


class Script(Tool):
    '''A simple wrapper that runs a shell script.
    :name: the path to the script to run.
    '''
    def __init__(self, name: Path):
        super().__init__(name=name.name, exec_name=str(name),
                         category=Categories.MISC)

    def check_available(self):
        return True


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
    rose_picker = Script(rose_picker_tool)
    rose_picker.run(additional_parameters=[str(rose_meta_conf),
                                           '-directory', str(config_dir),
                                           '-include_dirs', lfric_source],
                    env=env)

    # "build_config_loaders"
    # builds a bunch of f90s from the json
    logger.info('GenerateNamelist')
    gen_namelist = Script(gen_namelist_tool)
    gen_namelist.run(additional_parameters=['-verbose',
                                            str(config_dir / 'rose-meta.json'),
                                            '-directory', str(config_dir)])

    # create configuration_mod.f90 in source root
    logger.info('GenerateLoader')
    gen_loader = Script(gen_loader_tool)
    names = [name.strip() for name in open(config_dir / 'config_namelists.txt').readlines()]
    configuration_mod_fpath = config.source_root / 'configuration_mod.f90'
    gen_loader.run(additional_parameters=[configuration_mod_fpath,
                                          *names])

    # create feign_config_mod.f90 in source root
    logger.info('GenerateFeigns')
    feign_config = Script(gen_feigns_tool)
    feign_config_mod_fpath = config.source_root / 'feign_config_mod.f90'
    feign_config.run(additional_parameters=[str(config_dir / 'rose-meta.json'),
                                            '-output', feign_config_mod_fpath])

    config._artefact_store.add(ArtefactSet.FORTRAN_BUILD_FILES,
                               [configuration_mod_fpath,
                                feign_config_mod_fpath ])


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

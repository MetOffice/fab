import logging
import os
import shutil
from typing import Optional
from pathlib import Path

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps import step
from fab.steps.find_source_files import find_source_files
from fab.tools import Category, Tool

logger = logging.getLogger('fab')


class Script(Tool):
    '''A simple wrapper that runs a shell script.
    :name: the path to the script to run.
    '''
    def __init__(self, name: Path):
        super().__init__(name=name.name, exec_name=str(name),
                         category=Category.MISC)

    def check_available(self):
        return True


# ============================================================================
@step
def configurator(config, lfric_source: Path, gpl_utils_source: Path, rose_meta_conf: Path, config_dir=None):

    rose_picker_tool = gpl_utils_source / 'rose_picker/rose_picker'
    gen_namelist_tool = lfric_source / 'infrastructure/build/tools/GenerateNamelist'
    gen_loader_tool = lfric_source / 'infrastructure/build/tools/GenerateLoader'
    gen_feigns_tool = lfric_source / 'infrastructure/build/tools/GenerateFeigns'
    config_dir = config_dir or config.source_root / 'configuration'
    config_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    rose_lfric_path = gpl_utils_source / 'lib/python'
    env['PYTHONPATH'] += f':{rose_lfric_path}'

    # rose picker
    # -----------
    # creates rose-meta.json and config_namelists.txt in
    # gungho/build
    logger.info('rose_picker')
    rose_picker = Script(rose_picker_tool)
    rose_picker.run(additional_parameters=[rose_meta_conf,
                                           '-directory', config_dir,
                                           '-include_dirs', lfric_source],
                    env=env)
    rose_meta = config_dir / 'rose-meta.json'

    # build_config_loaders
    # --------------------
    # builds a bunch of f90s from the json
    logger.info('GenerateNamelist')
    gen_namelist = Script(gen_namelist_tool)
    gen_namelist.run(additional_parameters=['-verbose', rose_meta,
                                            '-directory', config_dir],
                     cwd=config_dir)

    # create configuration_mod.f90 in source root
    # -------------------------------------------
    logger.info('GenerateLoader')
    names = [name.strip() for name in
             open(config_dir / 'config_namelists.txt').readlines()]
    configuration_mod_fpath = config_dir / 'configuration_mod.f90'
    gen_loader = Script(gen_loader_tool)
    gen_loader.run(additional_parameters=[configuration_mod_fpath,
                                          *names])

    # create feign_config_mod.f90 in source root
    # ------------------------------------------
    logger.info('GenerateFeigns')
    feign_config_mod_fpath = config_dir / 'feign_config_mod.f90'
    gft = Script(gen_feigns_tool)
    gft.run(additional_parameters=[rose_meta,
                                   '-output', feign_config_mod_fpath])

    find_source_files(config, source_root=config_dir)


# ============================================================================
@step
def fparser_workaround_stop_concatenation(config):
    """
    fparser can't handle string concat in a stop statement. This step is
    a workaround.

    https://github.com/stfc/fparser/issues/330

    """
    feign_path = None
    for file_path in config.artefact_store[ArtefactSet.FORTRAN_BUILD_FILES]:
        if file_path.name == 'feign_config_mod.f90':
            feign_path = file_path
            break
    else:
        raise RuntimeError("Could not find 'feign_config_mod.f90'.")

    # rename "broken" version
    broken_version = feign_path.with_suffix('.broken')
    shutil.move(feign_path, broken_version)

    # make fixed version
    bad = "_config: '// &\n        'Unable to close temporary file'"
    good = "_config: Unable to close temporary file'"

    open(feign_path, 'wt').write(
        open(broken_version, 'rt').read().replace(bad, good))


# ============================================================================
def get_transformation_script(fpath: Path,
                              config: BuildConfig) -> Optional[Path]:
    ''':returns: the transformation script to be used by PSyclone.
    '''

    optimisation_path = config.source_root / 'optimisation' / 'meto-spice'
    relative_path = None
    for base_path in [config.source_root, config.build_output]:
        try:
            relative_path = fpath.relative_to(base_path)
        except ValueError:
            pass
    if relative_path:
        local_transformation_script = (optimisation_path /
                                       (relative_path.with_suffix('.py')))
        if local_transformation_script.exists():
            return local_transformation_script

    global_transformation_script = optimisation_path / 'global.py'
    if global_transformation_script.exists():
        return global_transformation_script
    return None

#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.steps.root_inc_files import RootIncFiles

from fab.config import Config

from fab.builder import Build
from fab.constants import SOURCE_ROOT
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import time_logger


def jules_config():

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'jules'

    config = Config(label='Jules Build', workspace=workspace)
    # config.use_multiprocessing = False
    config.debug_skip = True

    # make this a step?
    config.grab_config = {
        ('src', '~/svn/jules/trunk/src'),
        ('util', '~/svn/jules/trunk/utils')
    }

    unreferenced_dependencies = [
        'sunny', 'solpos', 'solang', 'redis', 'init_time', 'init_irrigation', 'init_urban', 'init_fire', 'init_drive',
        'init_imogen', 'init_prescribed_data', 'init_vars_tmp', 'imogen_check', 'imogen_update_clim', 'control',
        'imogen_update_carb', 'next_time', 'sow', 'emerge', 'develop', 'partition', 'radf_co2', 'radf_non_co2',
        'adf_ch4gcm_anlg', 'drdat', 'clim_calc', 'diffcarb_land_co2', 'ocean_co2', 'diffcarb_land_ch4',
        'diff_atmos_ch4', 'day_calc', 'response', 'radf_ch4', 'gcm_anlg', 'delta_temp', 'rndm', 'invert', 'vgrav',
        'conversions_mod', 'water_constants_mod', 'planet_constants_mod', 'veg_param_mod', 'flake_interface'
    ]

    config.steps = [

        FindSourceFiles(workspace / SOURCE_ROOT, file_filtering=[
            (['src/control/um/'], False),
            (['src/initialisation/um/'], False),
            (['src/params/shared/cable_maths_constants_mod.F90'], False)]),

        RootIncFiles(workspace / SOURCE_ROOT),

        CPreProcessor(),

        FortranPreProcessor(
            preprocessor='cpp',
            common_flags=['-traditional-cpp', '-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I', '$output']
        ),

        Analyse(root_symbol='jules', unreferenced_deps=unreferenced_dependencies),
        # Analyse(),

        CompileC(),

        CompileFortran(
            compiler=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
            common_flags=[
                '-c',
                '-J', '$output'],

        ),
        LinkExe(
            linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
            output_fpath='$output/jules.exe',
            flags=['-lm']),
    ]
    return config


def main():

    logger = logging.getLogger('fab')
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    config = jules_config()

    # ignore this, it's not here
    with time_logger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)

    Build(config=config, ).run()


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


if __name__ == '__main__':
    main()

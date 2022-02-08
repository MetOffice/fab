#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.steps.root_inc_files import RootIncFiles

from fab.config import ConfigSketch

from fab.builder import Build
from fab.constants import SOURCE_ROOT
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import GetSourceFiles
from fab.util import time_logger


def jules_config():

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'jules'

    config = ConfigSketch(label='Jules Build', workspace=workspace)
    # config.use_multiprocessing = False
    config.debug_skip = True

    # make this a step?
    config.grab_config = {
        ('src', '~/svn/jules/trunk/src'),
        ('util', '~/svn/jules/trunk/utils')
    }

    unreferenced_dependencies = [
        'sunny', 'solpos', 'solang', 'redis', 'init_time', 'init_urban', 'init_fire',
        'init_drive', 'init_imogen', 'init_prescribed_data', 'init_vars_tmp', 'imogen_check',
        'imogen_update_clim', 'control', 'imogen_update_carb', 'next_time', 'sow', 'emerge', 'develop',
        'partition', 'radf_co2', 'radf_non_co2', 'adf_ch4gcm_anlg', 'drdat', 'clim_calc', 'diffcarb_land_co2',
        'ocean_co2', 'diffcarb_land_ch4', 'diff_atmos_ch4', 'day_calc', 'response', 'radf_ch4', 'gcm_anlg',
        'delta_temp', 'rndm', 'invert', 'vgrav', 'conversions_mod', 'water_constants_mod', 'planet_constants_mod',
        'veg_param_mod', 'flake_interface'
    ]

    config.steps = [

        GetSourceFiles(workspace / SOURCE_ROOT, file_filtering=[
            (['src/control/um/'], False),
            (['src/initialisation/um/'], False),
            (['src/params/shared/cable_maths_constants_mod.F90'], False)]),

        RootIncFiles(workspace / SOURCE_ROOT),

        CPreProcessor(),

        FortranPreProcessor(
            preprocessor='cpp',
            common_flags=['-traditional-cpp', '-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I', '$output']
        ),

        Analyse(unreferenced_deps=unreferenced_dependencies),
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
            flags='-lm'),
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


######################

# import logging
# import os
# import shutil
# from pathlib import Path
#
# from fab.builder import Build
# from fab.constants import SOURCE_ROOT


# def main():
#     # config
#     project_name = "jules"
#     src_paths = {
#         os.path.expanduser("~/svn/jules/trunk/src"): "src",
#         os.path.expanduser("~/svn/jules/trunk/utils"): "utils",
#     }
#
#     #
#     workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name
#
#     # TODO: This will be part of grab/extract
#     # Copy all source into workspace
#     for src_path, label in src_paths.items():
#         shutil.copytree(src_path, workspace / SOURCE_ROOT / label, dirs_exist_ok=True)
#
#     config = read_config("jules.config")
#     settings = config['settings']
#     flags = config['flags']
#
#     my_fab = Build(workspace=workspace,
#                    target=settings['target'],
#                    exec_name=settings['exec-name'],
#                    fpp_flags=flags['fpp-flags'],
#                    fc_flags=flags['fc-flags'],
#                    ld_flags=flags['ld-flags'],
#                    n_procs=3,
#                    stop_on_error=True,
#                    skip_files=config.skip_files,
#                    unreferenced_deps=config.unreferenced_deps,
#                    # use_multiprocessing=False,
#                    # debug_skip=True,
#                    include_paths=config.include_paths)
#
#     logger = logging.getLogger('fab')
#     # logger.setLevel(logging.DEBUG)
#     logger.setLevel(logging.INFO)
#
#     my_fab.run()
#
#
# if __name__ == '__main__':
#     main()

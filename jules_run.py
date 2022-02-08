#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.config import ConfigSketch, AddFlags

from fab.builder import Build
from fab.constants import BUILD_SOURCE, SOURCE_ROOT, BUILD_OUTPUT
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import WalkSource
from fab.util import time_logger, file_walk


def jules_config():

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'jules'

    config = ConfigSketch(label='Jules Build', workspace=workspace)
    config.use_multiprocessing = False

    config.grab_config = {
        ('src', '~/svn/jules/trunk/src'),
        ('util', '~/svn/jules/trunk/utils')
    }

    config.extract_config = [
        (['src/control/um/'], False),
        (['src/initialisation/um/'], False),
        (['src/params/shared/cable_maths_constants_mod.f90'], False),
    ]

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
        WalkSource(workspace / BUILD_SOURCE),
        CPreProcessor(),
        FortranPreProcessor(
            preprocessor='cpp',
            common_flags=['-traditional-cpp', '-P','-DMPI_DUMMY', '-DNCDF_DUMMY', '-I', '$source',
            ]
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

    # ignore this, it's not here
    config = jules_config()

    with time_logger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)

    with time_logger("extracting"):
        extract_will_do_this(config.extract_config, config.workspace)

    Build(config=config, ).run()


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )

class PathFilter(object):
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include = include

    def check(self, path):
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


def extract_will_do_this(path_filters, workspace):
    source_folder = workspace / SOURCE_ROOT
    build_tree = workspace / BUILD_SOURCE

    # tuples to objects
    path_filters = [PathFilter(*i) for i in path_filters]

    for fpath in file_walk(source_folder):

        include = True
        for path_filter in path_filters:
            res = path_filter.check(fpath)
            if res is not None:
                include = res

        # copy it to the build folder?
        if include:
            rel_path = fpath.relative_to(source_folder)
            dest_path = build_tree / rel_path
            # make sure the folder exists
            if not dest_path.parent.exists():
                os.makedirs(dest_path.parent)

            if dest_path.suffix == '.inc':
                shutil.copy(fpath, workspace / BUILD_SOURCE)
            else:
                shutil.copy(fpath, dest_path)
        # else:
        #     print("excluding", fpath)

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

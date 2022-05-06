##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os
from argparse import ArgumentParser

from fab.steps.preprocess import CPreProcessor, FortranPreProcessor

from fab.build_config import BuildConfig, AddFlags
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFcm
from fab.steps.link_exe import LinkExe
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.walk_source import FindSourceFiles, EXCLUDE


def jules_config(revision=None):

    config = BuildConfig(project_label=f'jules_{revision}')
    # config.multiprocessing = False
    # config.debug_skip = True

    logger = logging.getLogger('fab')
    logger.info(f'building jules revision {revision}')
    logger.info(f"OMPI_FC is {os.environ.get('OMPI_FC') or 'not defined'}")

    # todo: there are likely to be config differences between revisions...
    # A big list of symbols which are used in jules without a use statement.
    # Fab doesn't automatically identify such dependencies, and so they must be specified here by the user.
    unreferenced_dependencies = [
        'sunny', 'solpos', 'solang', 'redis', 'init_time', 'init_irrigation', 'init_urban', 'init_fire', 'init_drive',
        'init_imogen', 'init_prescribed_data', 'init_vars_tmp', 'imogen_check', 'imogen_update_clim', 'control',
        'imogen_update_carb', 'next_time', 'sow', 'emerge', 'develop', 'partition', 'radf_co2', 'radf_non_co2',
        'adf_ch4gcm_anlg', 'drdat', 'clim_calc', 'diffcarb_land_co2', 'ocean_co2', 'diffcarb_land_ch4',
        'diff_atmos_ch4', 'day_calc', 'response', 'radf_ch4', 'gcm_anlg', 'delta_temp', 'rndm', 'invert', 'vgrav',
        'conversions_mod', 'water_constants_mod', 'planet_constants_mod', 'veg_param_mod', 'flake_interface']

    config.steps = [

        GrabFcm(src=f'fcm:jules.xm_tr/src', revision=revision, dst_label='src'),
        GrabFcm(src=f'fcm:jules.xm_tr/utils', revision=revision, dst_label='utils'),

        FindSourceFiles(file_filtering=[
            (['src/control/um/'], EXCLUDE),
            (['src/initialisation/um/'], EXCLUDE),
            (['src/control/rivers-standalone/'], EXCLUDE),
            (['src/initialisation/rivers-standalone/'], EXCLUDE),
            (['src/params/shared/cable_maths_constants_mod.F90'], EXCLUDE)]),

        RootIncFiles(),

        CPreProcessor(),

        FortranPreProcessor(
            preprocessor='cpp',
            common_flags=['-traditional-cpp', '-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output']),

        Analyse(root_symbol='jules', unreferenced_deps=unreferenced_dependencies),

        CompileC(),

        CompileFortran(
            compiler='gfortran',
            common_flags=['-c', '-J', '$output'],
            path_flags=[
                AddFlags('*/io/dump/read_dump_mod.f90', ['-fallow-argument-mismatch'])
            ]),

        LinkExe(
            linker='mpifort',
            output_fpath='$output/../jules.exe',
            flags=['-lm']),
    ]

    return config


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('JULES_REVISION', 'vn6.3'))
    args = arg_parser.parse_args()

    jules_config(revision=args.revision).run()

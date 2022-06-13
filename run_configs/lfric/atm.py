#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import logging
import os
from turtledemo import rosette

from fab.build_config import BuildConfig
from fab.constants import BUILD_OUTPUT
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder, GrabFcm
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles, EXCLUDE
from grab_lfric import lfric_source_config, gpl_utils_source_config
from run_configs.lfric.lfric_common import \
    Configurator, FparserWorkaround_StopConcatenation, psyclone_preprocessor, Psyclone

logger = logging.getLogger('fab')


# todo: optimisation path stuff


def atm_config():
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    config = BuildConfig(
        project_label='atm',
        # config.multiprocessing=False,
        reuse_artefacts=True,
    )

    config.steps = [

        # todo: put meaningful names because they all go into the same folder, so the auto-naming is the same for all
        # Importing internal dependencies
        GrabFolder(src=lfric_source / 'infrastructure/source/', dst_label='lfric', name='infrastructure/source'),
        GrabFolder(src=lfric_source / 'components/driver/source/', dst_label='lfric', name='components/driver/source'),
        GrabFolder(src=lfric_source / 'components/science/source/', dst_label='lfric', name='components/science/source'),
        GrabFolder(src=lfric_source / 'components/lfric-xios/source/', dst_label='lfric', name='components/lfric-xios/source'),

        # Extracting coupler - oasis component
        GrabFolder(src=lfric_source / 'components/coupler-oasis/source/', dst_label='lfric', name='components/coupler-oasis/source'),

        # Extracting Gungho dynamical core
        GrabFolder(src=lfric_source / 'gungho/source/', dst_label='lfric', name='gungho/source'),

        # Extracting UM physics
        GrabFcm(src='fcm:um.xm_tr/src', dst_label='um', revision=109936),
        GrabFcm(src='fcm:jules.xm_tr/src', dst_label='jules', revision=23182),
        GrabFcm(src='fcm:socrates.xm_tr/src', dst_label='socrates', revision='um12.2'),
        GrabFcm(src='fcm:shumlib.xm_tr/', dst_label='shumlib', revision='um12.2'),
        GrabFcm(src='fcm:casim.xm_tr/src', dst_label='casim', revision='um12.2'),

        GrabFolder(src=lfric_source / 'um_physics/source/', dst_label='lfric', name='um_physics/source'),
        GrabFolder(src=lfric_source / 'socrates/source/', dst_label='lfric', name='socrates/source'),
        GrabFolder(src=lfric_source / 'jules/source/', dst_label='lfric', name='jules/source'),

        # Extracting lfric_atm
        GrabFolder(src=lfric_source / 'lfric_atm/source/', dst_label='lfric', name='lfric_atm/source'),


        # generate more source files in source and source/configuration
        Configurator(lfric_source=lfric_source,
                     gpl_utils_source=gpl_utils_source,
                     rose_meta_conf=lfric_source / 'lfric_atm/rose-meta/lfric-lfric_atm/HEAD/rose-meta.conf',
                     config_dir=config.source_root / 'lfric/configuration'),

        # # todo: allow a single string
        # FindSourceFiles(file_filtering=[
        #     (['unit-test', '/test/'], EXCLUDE),
        #
        #     # (['src/atmosphere/convection/comorph'], EXCLUDE),
        #
        # ]),
        #
        # fortran_preprocessor(preprocessor='cpp -traditional-cpp', common_flags=['-P']),
        #
        # psyclone_preprocessor(),
        #
        # Psyclone(kernel_roots=[config.project_workspace / BUILD_OUTPUT]),
        #
        # FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),
        #
        # Analyse(
        #     root_symbol='lfric_atm',
        #     ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        # ),
        #
        # CompileFortran(
        #     compiler=os.getenv('FC', 'gfortran'),
        #     common_flags=['-c', '-J', '$output']),
        #
        # ArchiveObjects(output_fpath='$output/objects.a'),
        #
        # LinkExe(
        #     linker='mpifort',
        #     flags=[
        #         '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',  # EXTERNAL_DYNAMIC_LIBRARIES
        #         '-lxios',  # EXTERNAL_STATIC_LIBRARIES
        #         '-lstdc++',
        #     ],
        # ),

    ]

    return config


if __name__ == '__main__':
    atm_config().run()

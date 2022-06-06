#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import logging
import os

from fab.steps.archive_objects import ArchiveObjects

from fab.steps.link_exe import LinkExe

from fab.steps.compile_fortran import CompileFortran

from fab.steps.analyse import Analyse

from fab.constants import BUILD_OUTPUT

from fab.build_config import BuildConfig
from fab.steps.grab import GrabFolder
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles
from grab_lfric import lfric_source, gpl_utils_source
from run_configs.lfric.lfric_common import Configurator, FparserWorkaround_StopConcatenation, psyclone_preprocessor, \
    Psyclone

logger = logging.getLogger('fab')


# todo: optimisation path stuff


def gungho():

    config = BuildConfig(project_label='gungho')
    # config.multiprocessing = False,
    config.reuse_artefacts = True

    lfric_source_config = lfric_source()
    config.steps = [

        GrabFolder(src=lfric_source_config.source_root / 'lfric/infrastructure/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/driver/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/science/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/components/lfric-xios/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/gungho/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/um_physics/source/kernel/stph/',
                   dst_label='um_physics/source/kernel/stph/'),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/um_physics/source/constants/',
                   dst_label='um_physics/source/constants'),

        # generate more source files in source and source/configuration
        Configurator(
            lfric_source=lfric_source_config.source_root / 'lfric',
            gpl_utils_source=gpl_utils_source().source_root / 'gpl_utils'),

        FindSourceFiles(file_filtering=[
            # todo: allow a single string
            (['unit-test', '/test/'], False),
        ]),

        fortran_preprocessor(preprocessor='cpp -traditional-cpp', common_flags=['-P']),

        psyclone_preprocessor(),

        Psyclone(kernel_roots=[config.project_workspace / BUILD_OUTPUT]),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol='gungho',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileFortran(
            compiler=os.getenv('FC', 'gfortran'),
            common_flags=['-c', '-J', '$output']),

        ArchiveObjects(output_fpath='$output/objects.a'),

        LinkExe(
            linker='mpifort',
            flags=[
                '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',  # EXTERNAL_DYNAMIC_LIBRARIES
                '-lxios',  # EXTERNAL_STATIC_LIBRARIES
                '-lstdc++',
            ],
        ),

    ]

    return config


if __name__ == '__main__':
    gungho_config = gungho()
    gungho_config.run()

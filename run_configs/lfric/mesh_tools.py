#!/usr/bin/env python3
import os

from fab.build_config import BuildConfig
from fab.constants import BUILD_OUTPUT
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles, Exclude
from lfric_common import Configurator, psyclone_preprocessor, Psyclone, FparserWorkaround_StopConcatenation
from grab_lfric import lfric_source_config, gpl_utils_source_config


def mesh_tools():
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    config = BuildConfig(project_label='mesh_tools')
    config.steps = [

        GrabFolder(src=lfric_source / 'infrastructure/source/', dst_label=''),
        GrabFolder(src=lfric_source / 'mesh_tools/source/', dst_label=''),
        GrabFolder(src=lfric_source / 'components/science/source/', dst_label=''),

        GrabFolder(src=lfric_source / 'gungho/source/', dst_label=''),

        # generate more source files in source and source/configuration
        Configurator(
            lfric_source=lfric_source,
            gpl_utils_source=gpl_utils_source,
            rose_meta_conf=lfric_source / 'mesh_tools/rose-meta/lfric-mesh_tools/HEAD/rose-meta.conf',
        ),

        FindSourceFiles(path_filters=[
            # todo: allow a single string
            Exclude('unit-test', '/test/'),
        ]),

        fortran_preprocessor(preprocessor='cpp -traditional-cpp', common_flags=['-P']),

        psyclone_preprocessor(),

        Psyclone(kernel_roots=[config.project_workspace / BUILD_OUTPUT]),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol=['cubedsphere_mesh_generator', 'planar_mesh_generator', 'summarise_ugrid'],
            # ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        # todo:
        # compile one big lump

        CompileFortran(compiler=os.getenv('FC', 'gfortran'), common_flags=['-c', '-J', '$output']),

        # ArchiveObjects(),

        # link the 3 trees' objects
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
    mesh_tools().run()

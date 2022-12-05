#!/usr/bin/env python3
from argparse import ArgumentParser

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.grab import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.find_source_files import FindSourceFiles, Exclude

from lfric_common import Configurator, FparserWorkaround_StopConcatenation
from fab.steps.psyclone import psyclone_preprocessor, Psyclone
from grab_lfric import lfric_source_config, gpl_utils_source_config


def mesh_tools_config(two_stage=False, opt='Og'):
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler()

    config = BuildConfig(project_label=f'mesh tools {compiler} {opt} {int(two_stage)+1}stage')
    config.steps = [

        GrabFolder(src=lfric_source / 'infrastructure/source/', dst=''),
        GrabFolder(src=lfric_source / 'mesh_tools/source/', dst=''),
        GrabFolder(src=lfric_source / 'components/science/source/', dst=''),

        GrabFolder(src=lfric_source / 'gungho/source/', dst=''),

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

        Psyclone(kernel_roots=[config.build_output]),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol=['cubedsphere_mesh_generator', 'planar_mesh_generator', 'summarise_ugrid'],
            # ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        # todo:
        # compile one big lump

        CompileFortran(
            common_flags=[
                '-c',
                f'-{opt}',
            ],
            two_stage_flag='-fsyntax-only' if two_stage else None,
        ),

        ArchiveObjects(),

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
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--two-stage', action='store_true')
    arg_parser.add_argument('-opt', default='Og', choices=['Og', 'O0', 'O1', 'O2', 'O3'])
    args = arg_parser.parse_args()

    mesh_tools_config(two_stage=args.two_stage, opt=args.opt).run()

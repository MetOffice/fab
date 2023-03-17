#!/usr/bin/env python3
from pathlib import Path

from fab.util import common_arg_parser

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import preprocess_fortran
from fab.steps.find_source_files import FindSourceFiles, Exclude
from fab.steps.psyclone import Psyclone, psyclone_preprocessor

from lfric_common import Configurator, FparserWorkaround_StopConcatenation
from grab_lfric import lfric_source_config, gpl_utils_source_config


def mesh_tools_config(two_stage=False, verbose=False):
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler()

    # this folder just contains previous output, for testing the overrides mechanism.
    psyclone_overrides = Path(__file__).parent / 'mesh_tools_overrides'

    config = BuildConfig(
        project_label=f'mesh tools {compiler} {int(two_stage)+1}stage',
        verbose=verbose,
    )
    config.steps = [

        GrabFolder(src=lfric_source / 'infrastructure/source/', dst=''),
        GrabFolder(src=lfric_source / 'mesh_tools/source/', dst=''),
        GrabFolder(src=lfric_source / 'components/science/source/', dst=''),

        GrabFolder(src=lfric_source / 'gungho/source/', dst=''),

        # grab the psyclone overrides folder into the source folder
        GrabFolder(src=psyclone_overrides, dst='mesh_tools_overrides'),

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

        preprocess_fortran(preprocessor='cpp -traditional-cpp', common_flags=['-P']),

        psyclone_preprocessor(common_flags=['-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DCOUPLED']),

        Psyclone(
            kernel_roots=[config.build_output],
            cli_args=['--config', Path(__file__).parent / 'psyclone.cfg'],
            overrides_folder=config.source_root / 'mesh_tools_overrides',
        ),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol=['cubedsphere_mesh_generator', 'planar_mesh_generator', 'summarise_ugrid'],
            # ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileFortran(
            common_flags=[
                '-c',
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
    arg_parser = common_arg_parser()
    args = arg_parser.parse_args()

    mesh_tools_config(two_stage=args.two_stage, verbose=args.verbose).run()

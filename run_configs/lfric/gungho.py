#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import logging

from fab.util import common_arg_parser

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.find_source_files import FindSourceFiles, Exclude
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import preprocess_fortran
from fab.steps.psyclone import Psyclone, preprocess_x90

from grab_lfric import lfric_source_config, gpl_utils_source_config
from lfric_common import Configurator, FparserWorkaround_StopConcatenation

logger = logging.getLogger('fab')


# todo: optimisation path stuff


def gungho_config(two_stage=False, verbose=False):
    lfric_source = lfric_source_config().source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config().source_root / 'gpl_utils'

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler()

    config = BuildConfig(
        project_label=f'gungho {compiler} {int(two_stage)+1}stage',
        verbose=verbose,
    )

    config.steps = [

        GrabFolder(src=lfric_source / 'infrastructure/source/', dst=''),
        GrabFolder(src=lfric_source / 'components/driver/source/', dst=''),
        GrabFolder(src=lfric_source / 'components/science/source/', dst=''),
        GrabFolder(src=lfric_source / 'components/lfric-xios/source/', dst=''),
        GrabFolder(src=lfric_source / 'gungho/source/', dst=''),

        # GrabFolder(src=lfric_source / 'um_physics/source/kernel/stph/', dst='um_physics/source/kernel/stph/'),
        # GrabFolder(src=lfric_source / 'um_physics/source/constants/', dst='um_physics/source/constants'),
        GrabFolder(src=lfric_source / 'um_physics/source/', dst=''),

        # generate more source files in source and source/configuration
        Configurator(
            lfric_source=lfric_source,
            gpl_utils_source=gpl_utils_source,
            rose_meta_conf=lfric_source / 'gungho/rose-meta/lfric-gungho/HEAD/rose-meta.conf',
        ),

        FindSourceFiles(path_filters=[Exclude('unit-test', '/test/')]),

        preprocess_fortran(
            preprocessor='cpp -traditional-cpp',
            common_flags=[
                '-P',
                '-DRDEF_PRECISION=64', '-DR_SOLVER_PRECISION=64', '-DR_TRAN_PRECISION=64', '-DUSE_XIOS',
            ]),

        preprocess_x90(common_flags=['-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DCOUPLED']),

        Psyclone(
            kernel_roots=[config.build_output],
            transformation_script=lfric_source / 'gungho/optimisation/meto-spice/global.py',
            cli_args=[],
        ),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol='gungho',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        CompileFortran(
            common_flags=[
                '-c',
                '-ffree-line-length-none', '-fopenmp',
                '-g',
                '-std=f2008',

                '-Wall', '-Werror=conversion', '-Werror=unused-variable', '-Werror=character-truncation',
                '-Werror=unused-value', '-Werror=tabs',

                '-DRDEF_PRECISION=64', '-DR_SOLVER_PRECISION=64', '-DR_TRAN_PRECISION=64',
                '-DUSE_XIOS', '-DUSE_MPI=YES',
            ],
            two_stage_flag='-fsyntax-only' if two_stage else None,
        ),

        ArchiveObjects(),

        LinkExe(
            linker='mpifort',
            flags=[
                '-fopenmp',

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

    gungho_config(two_stage=args.two_stage, verbose=args.verbose).run()

#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os
from argparse import ArgumentParser

from fab.steps.archive_objects import ArchiveObjects

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFcm
from fab.steps.link import LinkExe
from fab.steps.preprocess import c_preprocessor, fortran_preprocessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.find_source_files import FindSourceFiles, Exclude

logger = logging.getLogger('fab')


def jules_config(revision=None, two_stage=False, opt='Og'):

    config = BuildConfig(project_label=f'jules {revision} {opt} {int(two_stage)+1}stage')
    # config.multiprocessing = False
    # config.reuse_artefacts = True

    logger.info(f'building jules revision {revision} {opt} {int(two_stage)+1}-stage')
    logger.info(f"OMPI_FC is {os.environ.get('OMPI_FC') or 'not defined'}")

    # todo: there are likely to be config differences between revisions...
    # A big list of symbols which are used in jules without a use statement.
    # Fab doesn't automatically identify such dependencies, and so they must be specified here by the user.
    unreferenced_dependencies = [
        # this is on a one-line if statement, which fab doesn't currently identify
        'imogen_update_carb',
    ]

    config.steps = [

        GrabFcm(src='fcm:jules.xm_tr/src', revision=revision, dst='src'),
        GrabFcm(src='fcm:jules.xm_tr/utils', revision=revision, dst='utils'),

        FindSourceFiles(path_filters=[
            Exclude('src/control/um/'),
            Exclude('src/initialisation/um/'),
            Exclude('src/control/rivers-standalone/'),
            Exclude('src/initialisation/rivers-standalone/'),
            Exclude('src/params/shared/cable_maths_constants_mod.F90'),
        ]),

        RootIncFiles(),

        fortran_preprocessor(
            preprocessor='cpp',
            common_flags=['-traditional-cpp', '-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output']
        ),

        Analyse(root_symbol='jules', unreferenced_deps=unreferenced_dependencies),

        CompileFortran(
            compiler='gfortran',
            common_flags=[
                '-c',
                '-J', '$output',
                f'-{opt}',
            ],
            two_stage_flag='-fsyntax-only' if two_stage else None,
            # required for newer compilers
            # path_flags=[
            #     AddFlags('*/io/dump/read_dump_mod.f90', ['-fallow-argument-mismatch']),
            # ]
        ),

        ArchiveObjects(),

        LinkExe(
            linker='mpifort',
            flags=['-lm', '-lnetcdff', '-lnetcdf']),
    ]

    return config


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('JULES_REVISION', 'vn6.3'))
    arg_parser.add_argument('--two-stage', action='store_true')
    arg_parser.add_argument('-opt', default='Og', choices=['Og', 'O0', 'O1', 'O2', 'O3'])
    args = arg_parser.parse_args()

    # logger.setLevel(logging.DEBUG)

    jules_config(revision=args.revision, two_stage=args.two_stage, opt=args.opt).run()

#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.cleanup_prebuilds import CleanupPrebuilds
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.find_source_files import FindSourceFiles, Exclude
from fab.steps.grab.fcm import FcmExport
from fab.steps.grab.prebuild import GrabPreBuild
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.root_inc_files import RootIncFiles
from fab.util import common_arg_parser

logger = logging.getLogger('fab')


def jules_config(revision=None, compiler=None, two_stage=False):

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler(compiler)
    config = BuildConfig(project_label=f'jules {revision} {compiler} {int(two_stage)+1}stage')

    logger.info(f'building jules {config.project_label}')
    logger.info(f"OMPI_FC is {os.environ.get('OMPI_FC') or 'not defined'}")

    two_stage_flag = None
    # todo: move this to the known compiler flags?
    if compiler == 'gfortran':
        if two_stage:
            two_stage_flag = '-fsyntax-only'

    # A big list of symbols which are used in jules without a use statement.
    # Fab doesn't automatically identify such dependencies, and so they must be specified here by the user.
    # Note: there are likely to be differences between revisions here...
    unreferenced_dependencies = [
        # this is on a one-line if statement, which fab doesn't currently identify
        'imogen_update_carb',
    ]

    config.steps = [

        FcmExport(src='fcm:jules.xm_tr/src', revision=revision, dst='src'),
        FcmExport(src='fcm:jules.xm_tr/utils', revision=revision, dst='utils'),

        # Copy another pre-build folder into our own.
        GrabPreBuild(path='/home/h02/bblay/temp_prebuild', allow_fail=True),

        FindSourceFiles(path_filters=[
            Exclude('src/control/um/'),
            Exclude('src/initialisation/um/'),
            Exclude('src/control/rivers-standalone/'),
            Exclude('src/initialisation/rivers-standalone/'),
            Exclude('src/params/shared/cable_maths_constants_mod.F90'),
        ]),

        RootIncFiles(),

        fortran_preprocessor(
            common_flags=['-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output']
        ),

        Analyse(root_symbol='jules', unreferenced_deps=unreferenced_dependencies),

        CompileFortran(
            compiler=compiler,
            two_stage_flag=two_stage_flag,
            # required for newer gfortran versions
            # path_flags=[
            #     AddFlags('*/io/dump/read_dump_mod.f90', ['-fallow-argument-mismatch']),
            # ]
        ),

        ArchiveObjects(),

        LinkExe(
            linker='mpifort',
            flags=['-lm', '-lnetcdff', '-lnetcdf']),

        CleanupPrebuilds(n_versions=1)
    ]

    return config


if __name__ == '__main__':
    arg_parser = common_arg_parser()
    arg_parser.add_argument('--revision', default=os.getenv('JULES_REVISION', 'vn6.3'))
    args = arg_parser.parse_args()

    jules_config(revision=args.revision, compiler=args.compiler, two_stage=args.two_stage).run()

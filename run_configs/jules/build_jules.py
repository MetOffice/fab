#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
import os
import shutil
import warnings
from pathlib import Path

from fab.build_config import BuildConfig
from fab.steps import step
from fab.steps.analyse import analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.cleanup_prebuilds import CleanupPrebuilds
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.find_source_files import find_source_files, Exclude
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.prebuild import GrabPreBuild
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.util import common_arg_parser, suffix_filter

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

    config.steps = [

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


@step
def root_inc_files(config):

    """
    Copy inc files into the workspace output root.

    Checks for name clash. This step does not create any artefacts.
    It's up to the user to configure other tools to find these files.

    :param artefact_store:
        Artefacts created by previous Steps.
        This is where we find the artefacts to process.
    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.

    """

    # todo: make the build output path a getter calculated in the config?
    build_output: Path = config.build_output
    build_output.mkdir(parents=True, exist_ok=True)

    warnings.warn("RootIncFiles is deprecated as .inc files are due to be removed.", DeprecationWarning)

    # inc files all go in the root - they're going to be removed altogether, soon
    inc_copied = set()
    for fpath in suffix_filter(config._artefact_store["all_source"], [".inc"]):

        # don't copy from the output root to the output root!
        # this is currently unlikely to happen but did in the past, and caused problems.
        if fpath.parent == build_output:
            continue

        # check for name clash
        if fpath.name in inc_copied:
            raise FileExistsError(f"name clash for inc file: {fpath}")

        logger.debug(f"copying inc file {fpath}")
        shutil.copy(fpath, build_output)
        inc_copied.add(fpath.name)


if __name__ == '__main__':
    arg_parser = common_arg_parser()
    arg_parser.add_argument('--revision', default=os.getenv('JULES_REVISION', 'vn6.3'))
    args = arg_parser.parse_args()

    config = jules_config(revision=args.revision, compiler=args.compiler, two_stage=args.two_stage)
    # this contains some of the stuff that was in run(), which needs to come before the steps.
    config._run_prep()

    # grab the source
    fcm_export(config, src='fcm:jules.xm_tr/src', revision=args.revision, dst_label='src')
    fcm_export(config, src='fcm:jules.xm_tr/utils', revision=args.revision, dst_label='utils')

    # find the source files
    find_source_files(config, path_filters=[
        Exclude('src/control/um/'),
        Exclude('src/initialisation/um/'),
        Exclude('src/control/rivers-standalone/'),
        Exclude('src/initialisation/rivers-standalone/'),
        Exclude('src/params/shared/cable_maths_constants_mod.F90'),
    ])

    # move inc files to the root for easy tool use
    root_inc_files(config)

    fortran_preprocessor(
        config,
        common_flags=['-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output']
    ),

    # A big list of symbols which are used in jules without a use statement.
    # Fab doesn't automatically identify such dependencies, and so they must be specified here by the user.
    # Note: there are likely to be differences between revisions here...
    unreferenced_dependencies = [
        # this is on a one-line if statement, which fab doesn't currently identify
        'imogen_update_carb',
    ]
    analyse(config, root_symbol='jules', unreferenced_deps=unreferenced_dependencies),

    config.run(prep=False)
    # we'll get rid of run() and call this here
    # config.finalise()

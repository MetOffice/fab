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
from fab.steps.archive_objects import archive_objects
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.compile_fortran import compile_fortran, get_fortran_compiler
from fab.steps.find_source_files import find_source_files, Exclude
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.prebuild import GrabPreBuild
from fab.steps.link import link_exe
from fab.steps.preprocess import fortran_preprocessor
from fab.util import common_arg_parser, suffix_filter

logger = logging.getLogger('fab')


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

    compiler, _ = get_fortran_compiler(args.compiler)
    config = BuildConfig(project_label=f'jules {args.revision} {compiler} {int(args.two_stage)+1}stage')

    logger.info(f'building jules {config.project_label}')
    logger.info(f"OMPI_FC is {os.environ.get('OMPI_FC') or 'not defined'}")

    two_stage_flag = None
    # todo: move this to the known compiler flags?
    if compiler == 'gfortran':
        if args.two_stage:
            two_stage_flag = '-fsyntax-only'

    # this contains some of the stuff that was in run(), which needs to come before the steps.
    # todo: make this a standalone func which creates the config, and call it state
    with config.context_thingymabob():

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

        fortran_preprocessor(config, common_flags=['-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output'])

        analyse(config, root_symbol='jules', unreferenced_deps=['imogen_update_carb']),

        compile_fortran(config, compiler=args.compiler, two_stage_flag=two_stage_flag)

        archive_objects(config),

        link_exe(config, linker='mpifort', flags=['-lm', '-lnetcdff', '-lnetcdf']),

        cleanup_prebuilds(config, n_versions=1)

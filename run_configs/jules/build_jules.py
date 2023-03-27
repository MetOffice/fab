#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging

from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files, Exclude
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.prebuild import grab_pre_build
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.steps.root_inc_files import root_inc_files

logger = logging.getLogger('fab')


if __name__ == '__main__':

    revision = 'vn6.3'

    with BuildConfig(project_label=f'jules {revision} $compiler') as config:
        # grab the source. todo: use some checkouts instead of exports in these configs.
        fcm_export(config, src='fcm:jules.xm_tr/src', revision=revision, dst_label='src')
        fcm_export(config, src='fcm:jules.xm_tr/utils', revision=revision, dst_label='utils')

        #
        grab_pre_build(config, path='/not/a/real/folder', allow_fail=True),

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

        preprocess_fortran(config, common_flags=['-P', '-DMPI_DUMMY', '-DNCDF_DUMMY', '-I$output'])

        analyse(config, root_symbol='jules', unreferenced_deps=['imogen_update_carb']),

        compile_fortran(config)

        archive_objects(config),

        link_exe(config, linker='mpifort', flags=['-lm', '-lnetcdff', '-lnetcdf']),

        cleanup_prebuilds(config, n_versions=1)

#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from fab.build_config import BuildConfig
from fab.steps.archive_objects import archive_objects
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from gcom_build_steps import common_build_steps


if __name__ == '__main__':

    with BuildConfig(project_label='gcom object archive $compiler') as config:
        common_build_steps(config)
        archive_objects(config, output_fpath='$output/libgcom.a')
        cleanup_prebuilds(config, all_unused=True)

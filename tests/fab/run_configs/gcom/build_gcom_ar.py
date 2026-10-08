#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.api import BuildConfig, ToolBox, archive_objects, cleanup_prebuilds
from gcom_build_steps import common_build_steps

if __name__ == "__main__":
    with BuildConfig(
        project_label="gcom object archive $compiler",
        mpi=True,
        openmp=False,
        tool_box=ToolBox(),
    ) as state:
        common_build_steps(state)
        archive_objects(state, output_fpath="$output/libgcom.a")
        cleanup_prebuilds(state, all_unused=True)

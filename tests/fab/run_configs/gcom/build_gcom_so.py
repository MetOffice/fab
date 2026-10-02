#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.api import (BuildConfig, cleanup_prebuilds, common_arg_parser,
                     link_shared_object, ToolBox)

from gcom_build_steps import common_build_steps


if __name__ == '__main__':

    arg_parser = common_arg_parser()
    # we can add our own arguments here
    parsed_args = arg_parser.parse_args()

    with BuildConfig(project_label='gcom shared library $compiler',
                     mpi=True, openmp=False, tool_box=ToolBox()) as state:
        common_build_steps(state, fpic=True)
        link_shared_object(state, output_fpath='$output/libgcom.so')
        cleanup_prebuilds(state, all_unused=True)

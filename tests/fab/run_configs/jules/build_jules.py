#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging

from fab.api import (analyse, archive_objects, BuildConfig, cleanup_prebuilds,
                     compile_fortran, Exclude, fcm_export, find_source_files,
                     grab_pre_build, Ifort, Linker, link_exe,
                     preprocess_fortran, root_inc_files, ToolBox)

logger = logging.getLogger('fab')


# TODO 312: we need to support non-intel compiler here.

class MpiIfort(Ifort):
    '''A small wrapper to make mpif90 available.'''
    def __init__(self):
        super().__init__(name="mpif90", exec_name="mpif90")


if __name__ == '__main__':

    revision = 'vn6.3'

    tool_box = ToolBox()
    # Create a new Fortran compiler MpiIfort
    fc = MpiIfort()
    tool_box.add_tool(fc)
    # Use the compiler as linker:
    tool_box.add_tool(Linker(compiler=fc))

    with BuildConfig(project_label=f'jules {revision} $compiler',
                     mpi=False, openmp=False, tool_box=tool_box) as state:
        # grab the source. todo: use some checkouts instead of exports
        # in these configs.
        fcm_export(state, src='fcm:jules.xm_tr/src', revision=revision,
                   dst_label='src')
        fcm_export(state, src='fcm:jules.xm_tr/utils', revision=revision,
                   dst_label='utils')

        grab_pre_build(state, path='/not/a/real/folder', allow_fail=True)

        # find the source files
        find_source_files(state, path_filters=[
            Exclude('src/control/um/'),
            Exclude('src/initialisation/um/'),
            Exclude('src/control/rivers-standalone/'),
            Exclude('src/initialisation/rivers-standalone/'),
            Exclude('src/params/shared/cable_maths_constants_mod.F90'),
        ])

        # move inc files to the root for easy tool use
        root_inc_files(state)

        preprocess_fortran(state, common_flags=['-P', '-DMPI_DUMMY',
                                                '-DNCDF_DUMMY', '-I$output'])

        analyse(state, root_symbol='jules',
                unreferenced_deps=['imogen_update_carb'])

        compile_fortran(state)

        archive_objects(state)

        link_exe(state, flags=['-lm', '-lnetcdff', '-lnetcdf'])

        cleanup_prebuilds(state, n_versions=1)

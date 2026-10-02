#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.api import (analyse, BuildConfig, compile_fortran, find_source_files,
                     git_checkout, Ifort, link_exe, Linker, preprocess_fortran,
                     ToolBox)


class MpiIfort(Ifort):
    '''A small wrapper to make mpiifort available.'''
    def __init__(self):
        super().__init__(name="mpifort", exec_name="mpifort")


if __name__ == '__main__':

    tool_box = ToolBox()
    # Create a new Fortran compiler MpiIfort
    fc = MpiIfort()
    tool_box.add_tool(fc)
    # Use the compiler as linker:
    tool_box.add_tool(Linker(compiler=fc))

    with BuildConfig(project_label='tiny_fortran $compiler',
                     tool_box=tool_box) as state:
        git_checkout(state, src='https://github.com/metomi/fab-test-data.git',
                     revision='main', dst_label='src')

        find_source_files(state)

        preprocess_fortran(state)

        analyse(state, root_symbol='my_prog')

        compile_fortran(state)
        link_exe(state)

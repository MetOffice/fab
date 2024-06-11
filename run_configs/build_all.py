#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

import os
from pathlib import Path

from fab.tools import Categories, Tool, ToolBox


class Script(Tool):
    '''A simple wrapper that runs a shell script.
    :name: the path to the script to run.
    '''
    def __init__(self, name: Path):
        super().__init__(name=name.name, exec_name=str(name),
                         category=Categories.MISC)

    def check_available(self):
        return True


# todo: run the exes, check the output
def build_all():

    tool_box = ToolBox()
    compiler = tool_box[Categories.FORTRAN_COMPILER]
    configs_folder = Path(__file__).parent

    os.environ['FAB_WORKSPACE'] = os.path.join(os.getcwd(), f'fab_build_all_{compiler.name}')

    scripts = [
        configs_folder / 'tiny_fortran/build_tiny_fortran.py',

        configs_folder / 'gcom/grab_gcom.py',
        configs_folder / 'gcom/build_gcom_ar.py',
        configs_folder / 'gcom/build_gcom_so.py',

        configs_folder / 'jules/build_jules.py',

        configs_folder / 'um/build_um.py',

        configs_folder / 'lfric/grab_lfric.py',
        configs_folder / 'lfric/mesh_tools.py',
        configs_folder / 'lfric/gungho.py',
        configs_folder / 'lfric/atm.py',
    ]

    # skip these for now, until we configure them to build again
    compiler_skip = {'gfortran': [], 'ifort': ['atm.py']}
    skip = compiler_skip[compiler.name]

    for script in scripts:
        script_tool = Script(script)
        # skip this build script for the current compiler?
        if script.name in skip:
            print(f''
                  f'-----'
                  f'SKIPPING {script.name} FOR COMPILER {compiler.name} - GET THIS COMPILING AGAIN'
                  f'-----')
            continue

        script_tool.run(capture_output=False)


if __name__ == '__main__':
    build_all()

#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import os
from pathlib import Path

from fab.steps.compile_fortran import get_compiler
from fab.util import run_command


def build_all():

    configs_folder = Path(__file__).parent
    compiler, _ = get_compiler()

    os.environ['FAB_WORKSPACE'] = os.path.join(os.getcwd(), f'fab_build_all_{compiler}')

    # CAUTION: This flag breaks jules rebuild. We haven't investigated this yet in depth. It's concerning.
    # os.environ['FAB_PREBUILD'] = os.path.join(os.environ['FAB_WORKSPACE'], '_prebuild')

    scripts = [
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
    compiler_skip = {'gfortran': [], 'ifort': ['build_um.py', 'atm.py']}
    skip = compiler_skip[compiler]

    for script in scripts:

        # skip this build script for the current compiler?
        if script.name in skip:
            print(f''
                  f'-----'
                  f'SKIPPING {script.name} FOR COMPILER {compiler} - GET THIS COMPILING AGAIN'
                  f'-----')
            continue

        run_command([script], capture_output=False)


if __name__ == '__main__':
    build_all()

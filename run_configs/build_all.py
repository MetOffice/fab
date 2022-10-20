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

    os.environ['FAB_WORKSPACE'] = os.path.join(os.getcwd(), 'fab_build_all')

    # We can speed up our builds by putting all projects' reusable artefacts in one big folder.
    # Note: Doesn't give benefit for analysis results across preprocessors
    #       because the two different preprocessors add blank lines differently.
    os.environ['FAB_PREBUILD'] = os.path.join(os.getcwd(), 'fab_prebuild')

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

    # skip these for now, until we configure them correctly
    compiler_skip = {'ifort': ['build_um.py']}
    compiler, _ = get_compiler()

    for script in scripts:

        # do we skip this script for the current compiler?
        for c, skip in compiler_skip.items():
            if compiler == c and script.name in scripts:
                print(f'skipping {script.name} for compiler {compiler} - get this compiling again!')
                continue

        run_command([script], capture_output=False)


if __name__ == '__main__':
    build_all()

# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.steps.analyse import analyse
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.tools import ToolBox

import pytest

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_minimal_fortran(tmp_path):

    # build
    with BuildConfig(fab_workspace=tmp_path, tool_box=ToolBox(),
                     project_label='foo', multiprocessing=False) as config:
        grab_folder(config, PROJECT_SOURCE)
        find_source_files(config)
        preprocess_fortran(config)
        analyse(config, root_symbol='test')
        with pytest.warns(UserWarning, match="Removing managed flag"):
            compile_fortran(config, common_flags=['-c'])
        link_exe(config, flags=['-lgfortran'])

    assert len(config.artefact_store[EXECUTABLES]) == 1

    # run
    command = [str(config.artefact_store[EXECUTABLES][0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output.strip() == 'Hello world!'

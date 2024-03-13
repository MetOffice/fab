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

import pytest

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_MinimalFortran(tmp_path):

    # build
    with BuildConfig(fab_workspace=tmp_path, project_label='foo', multiprocessing=False) as config, \
         pytest.warns(UserWarning, match="removing managed flag"):
        grab_folder(config, PROJECT_SOURCE),
        find_source_files(config),
        preprocess_fortran(config),
        analyse(config, root_symbol='test'),
        compile_fortran(config, common_flags=['-c']),
        link_exe(config, linker='gcc', flags=['-lgfortran']),

    assert len(config._artefact_store[EXECUTABLES]) == 1

    # run
    command = [str(config._artefact_store[EXECUTABLES][0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output.strip() == 'Hello world!'

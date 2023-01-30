# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.steps.grab import GrabFolder

from fab.steps.compile_fortran import CompileFortran

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.steps.analyse import Analyse
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_MinimalFortran(tmp_path):

    # build
    config = BuildConfig(
        fab_workspace=tmp_path,
        project_label='foo',
        multiprocessing=False,

        steps=[
            GrabFolder(PROJECT_SOURCE),
            FindSourceFiles(),
            fortran_preprocessor(),
            Analyse(root_symbol='test'),
            CompileFortran(compiler='gfortran', common_flags=['-c']),
            LinkExe(linker='gcc', flags=['-lgfortran']),
        ],
    )
    config.run()
    assert len(config._artefact_store[EXECUTABLES]) == 1

    # run
    command = [str(config._artefact_store[EXECUTABLES][0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output.strip() == 'Hello world!'

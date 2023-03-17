# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.steps.analyse import Analyse
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import preprocess_c

PROJECT_SOURCE = Path(__file__).parent / 'project-source'


def test_CUseHeader(tmp_path):

    # build
    config = BuildConfig(
        fab_workspace=tmp_path,
        project_label='foo',
        multiprocessing=False,

        steps=[
            GrabFolder(PROJECT_SOURCE),

            FindSourceFiles(),

            CPragmaInjector(),
            preprocess_c(),
            Analyse(root_symbol='main'),
            CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),

            LinkExe(linker='gcc', flags=['-lgfortran']),
        ],
    )
    config.run()
    assert len(config._artefact_store[EXECUTABLES]) == 1

    # run
    command = [str(config._artefact_store[EXECUTABLES][0])]
    res = subprocess.run(command, capture_output=True)
    output = res.stdout.decode()
    assert output == ''.join(open(PROJECT_SOURCE / 'expected.exec.txt').readlines())

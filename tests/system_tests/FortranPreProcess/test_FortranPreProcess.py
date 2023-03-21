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
from fab.steps.compile_fortran import CompileFortran
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import preprocess_fortran


def make_config(fab_workspace, fpp_flags=None):
    return BuildConfig(
        fab_workspace=fab_workspace,
        project_label='foo',
        multiprocessing=False,
        steps=[
            GrabFolder(Path(__file__).parent / 'project-source'),
            FindSourceFiles(),
            preprocess_fortran(preprocessor='cpp -traditional-cpp', common_flags=fpp_flags),
            Analyse(root_symbol=['stay_or_go_now']),
            CompileFortran(compiler='gfortran', common_flags=['-c']),
            LinkExe(linker='gcc', flags=['-lgfortran']),
        ],
    )


def test_FortranPreProcess(tmp_path):

    # stay
    stay_config = make_config(fab_workspace=tmp_path, fpp_flags=['-P', '-DSHOULD_I_STAY=yes'])
    stay_config.run()

    stay_exe = stay_config._artefact_store[EXECUTABLES][0]
    stay_res = subprocess.run(str(stay_exe), capture_output=True)
    assert stay_res.stdout.decode().strip() == 'I should stay'

    # go
    go_config = make_config(fab_workspace=tmp_path, fpp_flags=['-P'])
    go_config.run()

    go_exe = go_config._artefact_store[EXECUTABLES][0]
    go_res = subprocess.run(str(go_exe), capture_output=True)
    assert go_res.stdout.decode().strip() == 'I should go now'

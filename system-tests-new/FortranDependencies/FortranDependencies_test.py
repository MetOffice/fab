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
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor, c_preprocessor
from fab.steps.walk_source import FindSourceFiles


def test_FortranDependencies(tmp_path):

    # build
    config = BuildConfig(
        fab_workspace=tmp_path,
        project_label='foo',
        source_root=Path(__file__).parent / 'project-source',
        multiprocessing=False,
        steps=[
            FindSourceFiles(),
            fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
            Analyse(root_symbol=['first', 'second']),
            CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),
            CompileFortran(compiler='gfortran', common_flags=['-c', '-J', '$output']),
            LinkExe(flags=['-lgfortran']),
        ],
    )
    config.run()
    assert len(config._artefact_store[EXECUTABLES]) == 2

    # run both
    expected = {
        'Hello               \n',
        'Good bye            \n',
    }
    actual = set()

    for exe in config._artefact_store[EXECUTABLES]:
        res = subprocess.run(exe, capture_output=True)
        actual.add(res.stdout.decode())

    assert actual == expected

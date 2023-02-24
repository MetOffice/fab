# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.parse.fortran import AnalysedFortran
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor


def test_FortranDependencies(tmp_path):

    # build
    config = BuildConfig(
        fab_workspace=tmp_path,
        project_label='foo',
        multiprocessing=False,
        steps=[
            GrabFolder(src=Path(__file__).parent / 'project-source'),
            FindSourceFiles(),
            fortran_preprocessor(),  # nothing to preprocess, actually, it's all little f90 files
            Analyse(root_symbol=['first', 'second']),
            CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),
            CompileFortran(compiler='gfortran', common_flags=['-c']),
            LinkExe(linker='gcc', flags=['-lgfortran']),
        ],
        verbose=True,
    )
    config.run()
    assert len(config._artefact_store[EXECUTABLES]) == 2

    # run both exes
    output = set()
    for exe in config._artefact_store[EXECUTABLES]:
        res = subprocess.run(str(exe), capture_output=True)
        output.add(res.stdout.decode())

    # check output
    assert output == {
        'Hello               \n',
        'Good bye            \n',
    }

    # check the analysis results
    assert AnalysedFortran.load(config.prebuild_folder / 'first.193489053.an') == AnalysedFortran(
        fpath=config.source_root / 'first.f90', file_hash=193489053,
        module_defs=None, symbol_defs={'first'},
        module_deps={'greeting_mod', 'constants_mod'}, symbol_deps={'greeting_mod', 'constants_mod', 'greet'})

    assert AnalysedFortran.load(config.prebuild_folder / 'two.2557739057.an') == AnalysedFortran(
        fpath=config.source_root / 'two.f90', file_hash=2557739057,
        module_defs=None, symbol_defs={'second'},
        module_deps={'constants_mod', 'bye_mod'}, symbol_deps={'constants_mod', 'bye_mod', 'farewell'})

    assert AnalysedFortran.load(config.prebuild_folder / 'greeting_mod.62446538.an') == AnalysedFortran(
        fpath=config.source_root / 'greeting_mod.f90', file_hash=62446538,
        module_defs={'greeting_mod'}, symbol_defs={'greeting_mod'},
        module_deps={'constants_mod'}, symbol_deps={'constants_mod'})

    assert AnalysedFortran.load(config.prebuild_folder / 'bye_mod.3332267073.an') == AnalysedFortran(
        fpath=config.source_root / 'bye_mod.f90', file_hash=3332267073,
        module_defs={'bye_mod'}, symbol_defs={'bye_mod'},
        module_deps={'constants_mod'}, symbol_deps={'constants_mod'})

    assert AnalysedFortran.load(config.prebuild_folder / 'constants_mod.233796393.an') == AnalysedFortran(
        fpath=config.source_root / 'constants_mod.f90', file_hash=233796393,
        module_defs={'constants_mod'}, symbol_defs={'constants_mod'},
        module_deps=None, symbol_deps=None)

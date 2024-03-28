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
from fab.steps.analyse import analyse
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran

import pytest


def test_FortranDependencies(tmp_path):

    # build
    with BuildConfig(fab_workspace=tmp_path, project_label='foo', multiprocessing=False) as config, \
         pytest.warns(UserWarning, match="removing managed flag"):
        grab_folder(config, src=Path(__file__).parent / 'project-source'),
        find_source_files(config),
        preprocess_fortran(config),  # nothing to preprocess, actually, it's all little f90 files
        analyse(config, root_symbol=['first', 'second']),
        compile_c(config, common_flags=['-c', '-std=c99']),
        compile_fortran(config, common_flags=['-c']),
        link_exe(config, linker='gcc', flags=['-lgfortran']),

    assert len(config.artefact_store[EXECUTABLES]) == 2

    # run both exes
    output = set()
    for exe in config.artefact_store[EXECUTABLES]:
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
        program_defs={'first'},
        module_defs=None, symbol_defs={'first'},
        module_deps={'greeting_mod', 'constants_mod'}, symbol_deps={'greeting_mod', 'constants_mod', 'greet'})

    assert AnalysedFortran.load(config.prebuild_folder / 'two.2557739057.an') == AnalysedFortran(
        fpath=config.source_root / 'two.f90', file_hash=2557739057,
        program_defs={'second'},
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

# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path
from typing import Dict

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse, get_previous_analyses, ANALYSIS_CSV, _load_analysis_file
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor, c_preprocessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import file_checksum


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
    output = set()
    for exe in config._artefact_store[EXECUTABLES]:
        res = subprocess.run(exe, capture_output=True)
        output.add(res.stdout.decode())

    # check output
    assert output == {
        'Hello               \n',
        'Good bye            \n',
    }

    # load and check the analysis csv
    analysis = _load_analysis_file(fpath=config.build_output / ANALYSIS_CSV)
    project_source = Path(__file__).parent / 'project-source'

    assert analysis == {
        project_source / 'first.f90': AnalysedFile(
            fpath=project_source / 'first.f90', file_hash=602051652,
            module_defs=None, symbol_defs={'first'},
            module_deps={'greeting_mod', 'constants_mod'}, symbol_deps={'greeting_mod', 'constants_mod', 'greet'}),
        project_source / 'two.f90': AnalysedFile(
            fpath=project_source / 'two.f90', file_hash=2677078225,
            module_defs=None, symbol_defs={'second'},
            module_deps={'constants_mod', 'bye_mod'}, symbol_deps={'constants_mod', 'bye_mod', 'farewell'}),
        project_source / 'greeting_mod.f90': AnalysedFile(
            fpath=project_source / 'greeting_mod.f90', file_hash=3589757085,
            module_defs={'greeting_mod'}, symbol_defs={'greeting_mod'},
            module_deps={'constants_mod'}, symbol_deps={'constants_mod'}),
        project_source / 'bye_mod.f90': AnalysedFile(
            fpath=project_source / 'bye_mod.f90', file_hash=3148775555,
            module_defs={'bye_mod'}, symbol_defs={'bye_mod'},
            module_deps={'constants_mod'}, symbol_deps={'constants_mod'}),
        project_source / 'constants_mod.f90': AnalysedFile(
            fpath=project_source / 'constants_mod.f90', file_hash=734401370,
            module_defs={'constants_mod'}, symbol_defs={'constants_mod'},
            module_deps=None, symbol_deps=None),
    }

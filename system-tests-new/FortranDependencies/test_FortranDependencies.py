# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import subprocess
from pathlib import Path

from fab.build_config import BuildConfig
from fab.constants import EXECUTABLES
from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse, ANALYSIS_CSV, _load_analysis_file
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.find_source_files import FindSourceFiles


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
            CompileFortran(compiler='gfortran', common_flags=['-c']),
            LinkExe(flags=['-lgfortran']),
        ],
    )
    config.run()
    assert len(config._artefact_store[EXECUTABLES]) == 2

    # run both
    output = set()
    for exe in config._artefact_store[EXECUTABLES]:
        res = subprocess.run(str(exe), capture_output=True)
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
            fpath=project_source / 'first.f90', file_hash=193489053,
            module_defs=None, symbol_defs={'first'},
            module_deps={'greeting_mod', 'constants_mod'}, symbol_deps={'greeting_mod', 'constants_mod', 'greet'}),
        project_source / 'two.f90': AnalysedFile(
            fpath=project_source / 'two.f90', file_hash=2557739057,
            module_defs=None, symbol_defs={'second'},
            module_deps={'constants_mod', 'bye_mod'}, symbol_deps={'constants_mod', 'bye_mod', 'farewell'}),
        project_source / 'greeting_mod.f90': AnalysedFile(
            fpath=project_source / 'greeting_mod.f90', file_hash=62446538,
            module_defs={'greeting_mod'}, symbol_defs={'greeting_mod'},
            module_deps={'constants_mod'}, symbol_deps={'constants_mod'}),
        project_source / 'bye_mod.f90': AnalysedFile(
            fpath=project_source / 'bye_mod.f90', file_hash=3332267073,
            module_defs={'bye_mod'}, symbol_defs={'bye_mod'},
            module_deps={'constants_mod'}, symbol_deps={'constants_mod'}),
        project_source / 'constants_mod.f90': AnalysedFile(
            fpath=project_source / 'constants_mod.f90', file_hash=233796393,
            module_defs={'constants_mod'}, symbol_defs={'constants_mod'},
            module_deps=None, symbol_deps=None),
    }

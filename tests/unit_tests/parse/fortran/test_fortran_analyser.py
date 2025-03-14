# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''Tests the Fortran analyser.
'''


from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import mock

from fparser.common.readfortran import FortranFileReader  # type: ignore
from fparser.two.Fortran2008 import Type_Declaration_Stmt  # type: ignore
from fparser.two.parser import ParserFactory  # type: ignore
from fparser.two.utils import walk  # type: ignore
import pytest

from fab.build_config import BuildConfig
from fab.parse import EmptySourceFile
from fab.parse.fortran import FortranAnalyser, AnalysedFortran
from fab.tools import ToolBox

# todo: test function binding


@pytest.fixture
def module_fpath() -> Path:
    '''Simple fixture that sets the name of the module test file.'''
    return Path(__file__).parent / "test_fortran_analyser.f90"


@pytest.fixture
def module_expected(module_fpath) -> AnalysedFortran:
    '''Returns the expected AnalysedFortran instance for the Fortran
    test module.'''
    return AnalysedFortran(
        fpath=module_fpath,
        file_hash=3737289404,
        module_defs={'foo_mod'},
        symbol_defs={'external_sub', 'external_func', 'foo_mod'},
        module_deps={'bar_mod', 'compute_chunk_size_mod'},
        symbol_deps={'monty_func', 'bar_mod', 'compute_chunk_size_mod'},
        file_deps=set(),
        mo_commented_file_deps={'some_file.c'},
    )


class TestAnalyser:

    @pytest.fixture
    def fortran_analyser(self, tmp_path):
        # Enable openmp, so fparser will handle the lines with omp sentinels
        config = BuildConfig('proj', ToolBox(),
                             fab_workspace=tmp_path, openmp=True)
        fortran_analyser = FortranAnalyser(config=config)
        return fortran_analyser

    def test_empty_file(self, fortran_analyser):
        # make sure we get back an EmptySourceFile
        with mock.patch('fab.parse.AnalysedFile.save'):
            analysis, artefact = fortran_analyser.run(
                fpath=Path(Path(__file__).parent / "empty.f90"))
        assert isinstance(analysis, EmptySourceFile)
        assert artefact is None

    def test_module_file(self, fortran_analyser, module_fpath,
                         module_expected):
        with mock.patch('fab.parse.AnalysedFile.save'):
            analysis, artefact = fortran_analyser.run(fpath=module_fpath)
        assert analysis == module_expected
        assert artefact == (fortran_analyser._config.prebuild_folder /
                            f'test_fortran_analyser.{analysis.file_hash}.an')

    def test_module_file_no_openmp(self, fortran_analyser, module_fpath,
                                   module_expected):
        '''Disable OpenMP, meaning the dependency on compute_chunk_size_mod
        should not be detected anymore.
        '''
        fortran_analyser.config._openmp = False
        with mock.patch('fab.parse.AnalysedFile.save'):
            analysis, artefact = fortran_analyser.run(fpath=module_fpath)

        # Without parsing openmp sentinels, the compute_chunk... symbols
        # must not be added:
        module_expected.module_deps.remove('compute_chunk_size_mod')
        module_expected.symbol_deps.remove('compute_chunk_size_mod')

        assert analysis == module_expected
        assert artefact == (fortran_analyser._config.prebuild_folder /
                            f'test_fortran_analyser.{analysis.file_hash}.an')

    def test_program_file(self, fortran_analyser, module_fpath,
                          module_expected):
        # same as test_module_file() but replacing MODULE with PROGRAM
        with NamedTemporaryFile(mode='w+t', suffix='.f90') as tmp_file:
            tmp_file.write(module_fpath.open().read().replace("MODULE",
                                                              "PROGRAM"))
            tmp_file.flush()
            with mock.patch('fab.parse.AnalysedFile.save'):
                analysis, artefact = fortran_analyser.run(
                    fpath=Path(tmp_file.name))

            module_expected.fpath = Path(tmp_file.name)
            module_expected._file_hash = 325155675
            module_expected.program_defs = {'foo_mod'}
            module_expected.module_defs = set()
            module_expected.symbol_defs.update({'internal_func',
                                                'internal_sub',
                                                'openmp_sentinel'})

            assert analysis == module_expected
            assert artefact == fortran_analyser._config.prebuild_folder \
                   / f'{Path(tmp_file.name).stem}.{analysis.file_hash}.an'


# todo: test more methods!

class TestProcessVariableBinding:
    '''This test class tests the variable binding.'''

    # todo: define and depend, with and without bind name

    def test_define_without_bind_name(self, tmp_path):
        '''Test usage of bind'''
        fpath = tmp_path / 'temp.f90'

        open(fpath, 'wt').write("""
            MODULE f_var

            USE, INTRINSIC :: ISO_C_BINDING

            IMPLICIT NONE
            PRIVATE

            CHARACTER(kind=c_char, len=1), &
              DIMENSION(12), BIND(c), TARGET, SAVE :: &
                helloworld=['H','e','L','l','O',' ','w','O','r','L','d','?']

            END MODULE f_var
        """)

        # parse
        reader = FortranFileReader(str(fpath), ignore_comments=False)
        f2008_parser = ParserFactory().create(std="f2008")
        tree = f2008_parser(reader)

        # find the tree node representing the variable binding
        var_decl = next(obj for obj in walk(tree)
                        if isinstance(obj, Type_Declaration_Stmt))

        # run our handler
        fpath = Path('foo')
        analysed_file = AnalysedFortran(fpath=fpath, file_hash=0)
        analyser = FortranAnalyser(config=None)
        analyser._process_variable_binding(analysed_file=analysed_file,
                                           obj=var_decl)

        assert analysed_file.symbol_defs == {'helloworld', }

    # todo: test named variable binding
    # def test_define_with_bind_name(self, tmp_path):
    #     pass

    # todo: test depending on a c variable, rather then defining one for c
    # def test_depend_foo(self):
    #     pass

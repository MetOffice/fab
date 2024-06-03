# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import mock

from fparser.common.readfortran import FortranFileReader  # type: ignore
from fparser.two.Fortran2008 import Type_Declaration_Stmt  # type: ignore
from fparser.two.parser import ParserFactory  # type: ignore
import pytest

from fab.build_config import BuildConfig
from fab.parse import EmptySourceFile
from fab.parse.fortran import FortranAnalyser, AnalysedFortran
from fab.parse.fortran_common import iter_content
from fab.tools import ToolBox


# todo: test function binding


@pytest.fixture
def module_fpath():
    return Path(__file__).parent / "test_fortran_analyser.f90"


@pytest.fixture
def module_expected(module_fpath):
    return AnalysedFortran(
        fpath=module_fpath,
        file_hash=1344519263,
        module_defs={'foo_mod'},
        symbol_defs={'external_sub', 'external_func', 'foo_mod'},
        module_deps={'bar_mod', 'compute_chunk_size_mod'},
        symbol_deps={'monty_func', 'bar_mod', 'compute_chunk_size_mod'},
        file_deps=set(),
        mo_commented_file_deps={'some_file.c'},
    )


class Test_Analyser(object):

    @pytest.fixture
    def fortran_analyser(self, tmp_path):
        fortran_analyser = FortranAnalyser()
        fortran_analyser._config = BuildConfig('proj', ToolBox(),
                                               fab_workspace=tmp_path)
        return fortran_analyser

    def test_empty_file(self, fortran_analyser):
        # make sure we get back an EmptySourceFile
        with mock.patch('fab.parse.AnalysedFile.save'):
            analysis, artefact = fortran_analyser.run(fpath=Path(Path(__file__).parent / "empty.f90"))
        assert type(analysis) is EmptySourceFile
        assert artefact is None

    def test_module_file(self, fortran_analyser, module_fpath, module_expected):
        with mock.patch('fab.parse.AnalysedFile.save'):
            analysis, artefact = fortran_analyser.run(fpath=module_fpath)
        assert analysis == module_expected
        assert artefact == fortran_analyser._config.prebuild_folder / f'test_fortran_analyser.{analysis.file_hash}.an'

    def test_program_file(self, fortran_analyser, module_fpath, module_expected):
        # same as test_module_file() but replacing MODULE with PROGRAM
        with NamedTemporaryFile(mode='w+t', suffix='.f90') as tmp_file:
            tmp_file.write(module_fpath.open().read().replace("MODULE", "PROGRAM"))
            tmp_file.flush()
            with mock.patch('fab.parse.AnalysedFile.save'):
                analysis, artefact = fortran_analyser.run(fpath=Path(tmp_file.name))

            module_expected.fpath = Path(tmp_file.name)
            module_expected._file_hash = 731743441
            module_expected.program_defs = {'foo_mod'}
            module_expected.module_defs = set()
            module_expected.symbol_defs.update({'internal_sub', 'openmp_sentinel', 'internal_func'})

            assert analysis == module_expected
            assert artefact == fortran_analyser._config.prebuild_folder \
                   / f'{Path(tmp_file.name).stem}.{analysis.file_hash}.an'


# todo: test more methods!

class Test_process_variable_binding(object):

    # todo: define and depend, with and without bind name

    def test_define_without_bind_name(self, tmp_path):
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
        var_decl = next(obj for obj in iter_content(tree) if isinstance(obj, Type_Declaration_Stmt))

        # run our handler
        fpath = Path('foo')
        analysed_file = AnalysedFortran(fpath=fpath, file_hash=0)
        analyser = FortranAnalyser()
        analyser._process_variable_binding(analysed_file=analysed_file, obj=var_decl)

        assert analysed_file.symbol_defs == {'helloworld', }

    # todo: test named variable binding
    # def test_define_with_bind_name(self, tmp_path):
    #     pass

    # todo: test depending on a c variable, rather then defining one for c
    # def test_depend_foo(self):
    #     pass

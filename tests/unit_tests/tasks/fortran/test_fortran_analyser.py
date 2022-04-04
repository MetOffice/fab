from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import mock
from unittest.mock import Mock

import pytest

from fab.dep_tree import AnalysedFile, EmptySourceFile
from fab.tasks.fortran import FortranAnalyser
from fab.util import HashedFile


# todo: test function binding


@pytest.fixture
def module_fpath():
    return Path(__file__).parent / "test_fortran_analyser.f90"


@pytest.fixture
def module_expected(module_fpath):
    return AnalysedFile(
        fpath=module_fpath,
        file_hash=None,
        symbol_deps={'monty_func', 'bar_mod'},
        symbol_defs={'external_sub', 'external_func', 'foo_mod'},
        file_deps=set(),
        mo_commented_file_deps={'some_file.c'},
    )


class Test_Analyser(object):

    def test_empty_file(self):
        mock_tree = Mock(content=[None])
        with mock.patch('fab.tasks.fortran.FortranAnalyser._parse_file', return_value=mock_tree):
            result = FortranAnalyser().run(HashedFile(fpath=None, file_hash=None))

        assert type(result) is EmptySourceFile

    def test_module_file(self, module_fpath, module_expected):
        result = FortranAnalyser().run(HashedFile(fpath=module_fpath, file_hash=None))
        assert result == module_expected

    def test_program_file(self, module_fpath, module_expected):
        # same as test_real_file() but replacing MODULE with PROGRAM
        with NamedTemporaryFile(mode='w+t', suffix='.f90') as tmp_file:
            tmp_file.write(module_fpath.open().read().replace("MODULE", "PROGRAM"))
            tmp_file.flush()
            result = FortranAnalyser().run(HashedFile(fpath=Path(tmp_file.name), file_hash=None))

            module_expected.fpath = Path(tmp_file.name)
            module_expected.symbol_defs.update({'internal_sub', 'internal_func'})

            assert result == module_expected

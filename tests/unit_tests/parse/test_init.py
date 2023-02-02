# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Test contents of parse/__init__.py

"""
import copy
from pathlib import Path

import pytest
from fab.parse import AnalysedFile
from fab.dep_tree import AnalysedDependent


class TestAnalysedFile(object):

    @pytest.fixture
    def analysed_file(self):
        return AnalysedFile(fpath=Path('foo.f90'), file_hash=123)

    @pytest.fixture
    def different_fpath(self):
        return AnalysedFile(fpath=Path('bar.f90'), file_hash=123)

    @pytest.fixture
    def different_file_hash(self):
        return AnalysedFile(fpath=Path('foo.f90'), file_hash=456)

    @pytest.fixture
    def as_dict(self):
        return {'fpath': 'foo.f90', 'file_hash': 123}

    def test_to_dict(self, analysed_file, as_dict):
        assert analysed_file.to_dict() == as_dict

    # eq
    def test_eq(self, analysed_file):
        assert analysed_file == copy.deepcopy(analysed_file)

    def test_eq_different_fpath(self, analysed_file, different_fpath):
        assert analysed_file != different_fpath

    def test_eq_different_file_hash(self, analysed_file, different_file_hash):
        assert analysed_file != different_file_hash

    # hash
    # We can't record the return value from self.hash() because it's different each time we invoke Python.
    def test_hash(self, analysed_file):
        assert hash(analysed_file) == hash(copy.deepcopy(analysed_file))

    def test_hash_different_fpath(self, analysed_file, different_fpath):
        assert hash(analysed_file) != hash(different_fpath)

    def test_hash_different_file_hash(self, analysed_file, different_file_hash):
        assert hash(analysed_file) != hash(different_file_hash)


class TestAnalysedDependent(object):

    @pytest.fixture
    def analysed_dependent(self):
        return AnalysedDependent(
            fpath=Path('foo.f90'),
            file_hash=123,
            symbol_defs={'my_func1', 'my_func2'},
            symbol_deps={'other_func1', 'other_func2'},
            file_deps={Path('other_file1.f90'), Path('other_file2.f90')},
        )

    @pytest.fixture
    def as_dict(self):
        return {
            'fpath': 'foo.f90',
            'file_hash': 123,
            'symbol_defs': ['my_func1', 'my_func2'],
            'symbol_deps': ['other_func1', 'other_func2'],
            'file_deps': ['other_file1.f90', 'other_file2.f90'],
        }

    @pytest.fixture
    def different_symbol_defs(self):
        return AnalysedDependent(
            fpath=Path('foo.f90'), file_hash=123,
            symbol_defs={'my_func3', 'my_func4'},
            symbol_deps={'other_func1', 'other_func2'},
            file_deps={Path('other_file1.f90'), Path('other_file1.f90')},
        )

    @pytest.fixture
    def different_symbol_deps(self):
        return AnalysedDependent(
            fpath=Path('foo.f90'), file_hash=123,
            symbol_defs={'my_func1', 'my_func2'},
            symbol_deps={'other_func3', 'other_func4'},
            file_deps={Path('other_file1.f90'), Path('other_file1.f90')},
        )

    @pytest.fixture
    def different_file_deps(self):
        return AnalysedDependent(
            fpath=Path('foo.f90'), file_hash=123,
            symbol_defs={'my_func1', 'my_func2'},
            symbol_deps={'other_func1', 'other_func2'},
            file_deps={Path('other_file3.f90'), Path('other_file4.f90')},
        )

    def test_add_symbol_def(self, analysed_dependent):
        analysed_dependent.add_symbol_def('my_func3')
        assert analysed_dependent.symbol_defs == {'my_func1', 'my_func2', 'my_func3'}

    def test_add_symbol_dep(self, analysed_dependent):
        analysed_dependent.add_symbol_dep('other_func3')
        assert analysed_dependent.symbol_deps == {'other_func1', 'other_func2', 'other_func3'}

    def test_add_file_dep(self, analysed_dependent):
        analysed_dependent.add_file_dep('other_file3.f90')
        assert analysed_dependent.file_deps == {
            Path('other_file1.f90'), Path('other_file2.f90'), Path('other_file3.f90')}

    def test_to_dict(self, analysed_dependent, as_dict):
        assert analysed_dependent.to_dict() == as_dict

    def test_from_dict(self, analysed_dependent, as_dict):
        assert AnalysedDependent.from_dict(as_dict) == analysed_dependent

    # eq
    def test_eq(self, analysed_dependent):
        assert analysed_dependent == copy.deepcopy(analysed_dependent)

    def test_eq_different_symbol_defs(self, analysed_dependent, different_symbol_defs):
        assert analysed_dependent != different_symbol_defs

    def test_eq_different_symbol_deps(self, analysed_dependent, different_symbol_deps):
        assert analysed_dependent != different_symbol_deps

    def test_eq_different_file_deps(self, analysed_dependent, different_file_deps):
        assert analysed_dependent != different_file_deps

    # hash
    def test_hash(self, analysed_dependent):
        assert hash(analysed_dependent) == hash(copy.deepcopy(analysed_dependent))

    def test_hash_different_symbol_defs(self, analysed_dependent, different_symbol_defs):
        assert hash(analysed_dependent) != hash(different_symbol_defs)

    def test_hash_different_symbol_deps(self, analysed_dependent, different_symbol_deps):
        assert hash(analysed_dependent) != hash(different_symbol_deps)

    def test_hash_different_file_deps(self, analysed_dependent, different_file_deps):
        assert hash(analysed_dependent) != hash(different_file_deps)

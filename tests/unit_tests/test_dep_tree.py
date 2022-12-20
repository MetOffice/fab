from pathlib import Path

import pytest

from fab.dep_tree import extract_sub_tree
from fab.parse import AnalysedFile


@pytest.fixture
def src_tree():
    return {
        Path('foo.f90'): AnalysedFile(fpath=Path('foo.f90'), file_hash=0),
        Path('root.f90'): AnalysedFile(
            fpath=Path('root.f90'), file_deps={Path('a.f90'), Path('b.f90')}, file_hash=0),
        Path('a.f90'): AnalysedFile(
            fpath=Path('a.f90'), file_deps={Path('c.f90')}, file_hash=0),
        Path('b.f90'): AnalysedFile(
            fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=0),
        Path('c.f90'): AnalysedFile(
            fpath=Path('c.f90'), file_deps=set(), file_hash=0),
    }


class Test_extract_sub_tree(object):

    def test_vanilla(self, src_tree):
        result = extract_sub_tree(source_tree=src_tree, root=Path('root.f90'))
        expect = src_tree.copy()
        del expect[Path('foo.f90')]
        assert result == expect

    # todo: check missing deps raise a message


class Test_AnalysedFile(object):

    def test_save_load(self, tmp_path):

        af = AnalysedFile(
            fpath=Path('/foo/bar.f90'), file_hash=123,
            module_defs={'bar_mod1', 'bar_mod2'}, symbol_defs={'bar_mod1', 'bar_mod2', 'bar_func1', 'bar_func2'},
            module_deps={'dep_mod1', 'dep_mod2'}, symbol_deps={'dep_mod1', 'dep_mod2', 'dep_func1', 'dep_func2'},
            file_deps={Path('file_dep1'), Path('file_dep2')}, mo_commented_file_deps={'c_dep1.c', 'c_dep2.c'},
        )

        fpath = tmp_path / 'foo.an'
        af.save(fpath)
        assert AnalysedFile.load(fpath) == af

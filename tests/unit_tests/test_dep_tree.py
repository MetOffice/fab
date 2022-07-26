from pathlib import Path

import pytest

from fab.dep_tree import AnalysedFile, extract_sub_tree


@pytest.fixture
def src_tree():
    return {
        Path('foo.f90'): AnalysedFile(fpath=Path('foo.f90'), file_hash=None),
        Path('root.f90'): AnalysedFile(
            fpath=Path('root.f90'), file_deps={Path('a.f90'), Path('b.f90')}, file_hash=None),
        Path('a.f90'): AnalysedFile(
            fpath=Path('a.f90'), file_deps={Path('c.f90')}, file_hash=None),
        Path('b.f90'): AnalysedFile(
            fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=None),
        Path('c.f90'): AnalysedFile(
            fpath=Path('c.f90'), file_deps=set(), file_hash=None),
    }


class Test_extract_sub_tree(object):

    def test_vanilla(self, src_tree):
        result = extract_sub_tree(source_tree=src_tree, root=Path('root.f90'))
        expect = src_tree.copy()
        del expect[Path('foo.f90')]
        assert result == expect

    # todo: check missing deps raise a message

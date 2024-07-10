from pathlib import Path

import pytest

from fab.dep_tree import extract_sub_tree, AnalysedDependent


@pytest.fixture
def src_tree():
    return {
        Path('foo.f90'): AnalysedDependent(fpath=Path('foo.f90'), file_hash=0),
        Path('root.f90'): AnalysedDependent(
            fpath=Path('root.f90'),
            file_deps={Path('a.f90'), Path('b.f90')},
            file_hash=0
        ),
        Path('a.f90'): AnalysedDependent(
            fpath=Path('a.f90'), file_deps={Path('c.f90')}, file_hash=0),
        Path('b.f90'): AnalysedDependent(
            fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=0),
        Path('c.f90'): AnalysedDependent(
            fpath=Path('c.f90'), file_deps=set(), file_hash=0),
    }


class Test_extract_sub_tree(object):

    def test_vanilla(self, src_tree):
        result = extract_sub_tree(source_tree=src_tree, root=Path('root.f90'))
        expect = src_tree.copy()
        del expect[Path('foo.f90')]
        assert result == expect

    # todo: check missing deps raise a message

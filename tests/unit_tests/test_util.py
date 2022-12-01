from pathlib import Path

import pytest

from fab.artefacts import CollectionConcat, SuffixFilter
from fab.util import suffix_filter


@pytest.fixture
def fpaths():
    return [
        Path('foo.F77'),
        Path('foo.f77'),
        Path('foo.F90'),
        Path('foo.f90'),
        Path('foo.c'),
    ]


class Test_suffix_filter(object):

    def test_vanilla(self, fpaths):
        result = suffix_filter(fpaths=fpaths, suffixes=['.F90', '.f90'])
        assert result == [Path('foo.F90'), Path('foo.f90')]


class TestCollectionConcat(object):

    def test_vanilla(self):
        getter = CollectionConcat(collections=[
            'fooz',
            SuffixFilter('barz', '.c')
        ])

        result = getter(artefact_store={
            'fooz': ['foo1', 'foo2'],
            'barz': [Path('bar.a'), Path('bar.b'), Path('bar.c')],
        })

        assert result == ['foo1', 'foo2', Path('bar.c')]


class TestSuffixFilter(object):

    def test_constructor_suffix_scalar(self):
        getter = SuffixFilter('barz', '.c')
        result = getter(artefact_store={'barz': [Path('bar.a'), Path('bar.b'), Path('bar.c')]})
        assert result == [Path('bar.c')]

    def test_constructor_suffix_vector(self):
        getter = SuffixFilter('barz', ['.b', '.c'])
        result = getter(artefact_store={'barz': [Path('bar.a'), Path('bar.b'), Path('bar.c')]})
        assert result == [Path('bar.b'), Path('bar.c')]



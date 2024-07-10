from pathlib import Path
from unittest import mock

import pytest

from fab.artefacts import CollectionConcat, SuffixFilter
from fab.util import input_to_output_fpath, suffix_filter, file_walk


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
        result = getter(artefact_store={'barz': [Path('bar.a'),
                                                 Path('bar.b'),
                                                 Path('bar.c')]})
        assert result == [Path('bar.c')]

    def test_constructor_suffix_vector(self):
        getter = SuffixFilter('barz', ['.b', '.c'])
        result = getter(artefact_store={'barz': [Path('bar.a'),
                                                 Path('bar.b'),
                                                 Path('bar.c')]})
        assert result == [Path('bar.b'), Path('bar.c')]


class Test_file_walk(object):

    @pytest.fixture
    def files(self, tmp_path):
        f = tmp_path / 'foo/bar/foo.txt'
        pbf = tmp_path / 'foo/bar/_prebuild/foo.txt'

        pbf.parent.mkdir(parents=True)
        f.touch()
        pbf.touch()

        return f, pbf

    def test_ignore(self, files, tmp_path):
        f, pbf = files

        result = list(file_walk(tmp_path / 'foo', ignore_folders=[pbf.parent]))
        assert result == [f]


class Test_input_to_output_fpath(object):

    @pytest.fixture
    def config(self):
        return mock.Mock(source_root=Path('/proj/source'),
                         build_output=Path('/proj/build_output'))

    def test_vanilla(self, config):
        input_path = Path('/proj/source/folder/file.txt')
        result = input_to_output_fpath(config, input_path)
        assert result == Path(config.build_output / 'folder/file.txt')

    def test_already_output(self, config):
        input_path = Path('/proj/build_output/folder/file.txt')
        result = input_to_output_fpath(config, input_path)
        assert result == input_path

    def test_outside_project(self, config):
        input_path = Path('/other/folder/file.txt')
        result = input_to_output_fpath(config, input_path)
        assert result == Path(config.build_output / 'other/folder/file.txt')

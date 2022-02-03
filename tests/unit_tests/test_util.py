from pathlib import Path

import pytest

from fab.util import suffix_filter, case_insensitive_replace


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


class Test_case_insensitive_replace(object):

    @pytest.fixture
    def sample_string(self):
        return "one foo foo four"

    def test_lower(self, sample_string):
        res = case_insensitive_replace(sample_string, "foo", "bar")
        assert res == "one bar bar four"

    def test_upper(self, sample_string):
        res = case_insensitive_replace(sample_string, "FOO", "bar")
        assert res == "one bar bar four"

    def test_mixed(self, sample_string):
        res = case_insensitive_replace(sample_string, "fOo", "bar")
        assert res == "one bar bar four"

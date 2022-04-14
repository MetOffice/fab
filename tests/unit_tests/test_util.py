from pathlib import Path
from unittest import mock

import pytest

from fab.util import suffix_filter, case_insensitive_replace, run_command


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


class Test_run_command(object):

    def test_no_error(self):
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.util.subprocess.run', return_value=mock_result):
            run_command(None)

    def test_error(self):
        mock_result = mock.Mock(returncode=1)
        mocked_error_message = 'mocked error message'
        mock_result.stderr.decode = mock.Mock(return_value=mocked_error_message)
        with mock.patch('fab.util.subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError) as err:
                run_command(None)
            assert mocked_error_message in str(err.value)

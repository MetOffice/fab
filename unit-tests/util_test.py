import pytest

from fab.util import case_insensitive_replace


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

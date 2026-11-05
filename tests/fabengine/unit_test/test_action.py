from pathlib import Path

from fabengine.actions import TwoPartPath
from pytest import raises


class TestTwoPartPath:
    def test_constructor(self):
        test_unit = TwoPartPath(Path("/var/tmp"), Path("cheese"))
        assert test_unit.root == Path("/var/tmp")
        assert test_unit.branch == Path("cheese")

    def test_constructor_bad_root(self):
        with raises(AssertionError):
            TwoPartPath(Path("teapot"), Path("beef"))

    def test_constructor_bad_branch(self):
        with raises(AssertionError):
            TwoPartPath(Path("/var/tmp"), Path("/dev/null"))

    def test_full(self):
        test_unit = TwoPartPath(Path("/var/tmp"), Path("wibble"))
        assert test_unit.full == Path("/var/tmp/wibble")

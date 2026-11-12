import atexit
import os
import sys
from multiprocessing import Array, Process

from pytest import importorskip, mark, raises, skip

setproctitle = importorskip("setproctitle")

import fabengine.cui.status
from fabengine.cui.status import set_ps_name, set_terminal_title


def check_settitle_works():
    """Check whether titles can be changed.

    This checks for problems with settitle when run in the test suite
    and allows tests to be skipped if the functionality is not
    available.
    """
    before = setproctitle.getproctitle()
    try:
        setproctitle.setproctitle("updated")
        after = setproctitle.getproctitle()
    finally:
        setproctitle.setproctitle(before)
    return before != after


if not check_settitle_works():
    skip("skipping settitle tests", allow_module_level=True)


class TestSetPsName:
    """Test functions to set process name."""

    def test_function(self):
        """Check simple funtion wrapper works."""

        before = setproctitle.getproctitle()

        @set_ps_name
        def func():
            return setproctitle.getproctitle()

        result = func()
        assert result != ""

        assert func() == "fabengine: TestSetPsName.test_function.<locals>.func"
        assert setproctitle.getproctitle() == before

    def test_exception(self):
        """Check exception restores previous title."""

        before = setproctitle.getproctitle()

        @set_ps_name
        def func():
            raise RuntimeError(setproctitle.getproctitle())

        with raises(RuntimeError) as excinfo:
            func()

        assert "fabengine: TestSetPsName.test_exception.<locals>.func" in str(
            excinfo.value
        )
        assert setproctitle.getproctitle() == before

    def test_unavailable(self, monkeypatch):
        """Check nothing breaks when functionality is not available."""

        monkeypatch.setattr(fabengine.cui.status, "__set_process_titles", False)

        before = setproctitle.getproctitle()

        @set_ps_name
        def func():
            return setproctitle.getproctitle()

        assert func() == before
        assert setproctitle.getproctitle() == before

    def test_method(self):
        """Check class method wrapper works."""

        before = setproctitle.getproctitle()

        class DummyClass:
            """Dummy action class."""

            @set_ps_name
            def check(self):
                """Method to return process name."""
                return setproctitle.getproctitle()

        dummy = DummyClass()

        assert (
            dummy.check()
            == "fabengine: TestSetPsName.test_method.<locals>.DummyClass.check"
        )
        assert setproctitle.getproctitle() == before

    def test_multiprocess(self):
        """Check subclasses of Process use name attribute."""

        before = setproctitle.getproctitle()
        padding = 32

        class Worker(Process):
            """Trivial Process subclass."""

            def __init__(self, name):
                super().__init__(name="WorkerTest", target=self._work, args=(name,))

            @set_ps_name
            def _work(self, value):
                """Worker function to save the docstring."""
                value.value = bytes(setproctitle.getproctitle()[:padding], "utf8")

        name = Array("c", b" " * padding)
        p = Worker(name)
        p.start()
        p.join()

        assert name.value == b"fabengine: WorkerTest"
        assert setproctitle.getproctitle() == before


class TestTerminalTitle:
    """Test functions to set terminal title."""

    def test_non_interactive(self, monkeypatch, capsys):
        """Check nothing is generated if output is not a terminal."""
        monkeypatch.setattr(os, "isatty", lambda x: False)
        monkeypatch.setattr(sys.stdout, "fileno", lambda: 1)

        set_terminal_title()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_dumb_terminal(self, monkeypatch, capsys):
        """Check nothing is generated if output is not xterm-like."""
        monkeypatch.setattr(os, "isatty", lambda x: True)
        monkeypatch.setattr(sys.stdout, "fileno", lambda: 1)
        monkeypatch.setitem(os.environ, "TERM", "dumb")

        set_terminal_title()
        captured = capsys.readouterr()
        assert captured.out == ""

    @mark.parametrize(
        "title, result", [(None, "fabengine"), ("Test", "fabengine: Test")]
    )
    def test_xterm_title(self, title, result, monkeypatch, capsys):

        monkeypatch.setattr(atexit, "register", lambda x: None)
        monkeypatch.setattr(os, "isatty", lambda x: True)
        monkeypatch.setattr(sys.stdout, "fileno", lambda: 1)
        monkeypatch.setitem(os.environ, "TERM", "xterm")

        set_terminal_title(title)
        captured = capsys.readouterr()

        assert "\033[22;0t" in captured.out
        assert f"\033]2;{result}\007" in captured.out

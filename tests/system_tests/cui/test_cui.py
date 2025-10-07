#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
System tests for the fab command line utility.
"""

import sys
import pytest
from pathlib import Path
from textwrap import dedent
import fab.cui.__main__


class TestArgsHandling:
    """Test the command line arguments."""

    def test_args_help(self, capsys: pytest.CaptureFixture) -> None:
        """Test list source of arguments."""

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--help"])
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "--file FILE" in captured.out

    def test_sys_help(
        self, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test sys.argv alternate source of arguments."""

        monkeypatch.setattr(sys, "argv", ["__main__.py", "--help"])

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main()
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "--file FILE" in captured.out


class TestUserTarget:
    """Test with a user-supplied target script."""

    def test_missing_file(self, capsys: pytest.CaptureFixture) -> None:
        """Test with a missing target file."""

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", "nosuch"])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "error: fab file does not exist" in captured.err

    def test_invalid_class_name(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test with an invalid build class name."""

        target = tmp_path / "invalid.py"

        target.write_text(
            """
from fab.target.base import FabTargetBase
class FabBuildInvalidName(FabTargetBase):
  def run(self, args):
    pass
            """
        )

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", str(target)])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "error: unable to find FabBuildTarget in" in captured.err

    def test_invalid_subclass(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test with an invalid subclass."""

        target = tmp_path / "invalid.py"

        target.write_text(
            dedent(
                """
                class FabBuildTarget:
                  def run(self, args):
                    pass
                """
            )
        )

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", str(target)])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "error: FabBuildTarget does not extend FabTargetBase" in captured.err

    def test_missing_project(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test subclass that lacks a project name is invalid."""

        target = tmp_path / "valid.py"

        target.write_text(
            dedent(
                """
                from fab.target.base import FabTargetBase
                class FabBuildTarget(FabTargetBase):
                  def run(self, args):
                    pass
                """
            )
        )

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", str(target)])

        assert exc.value.code == 10

        captured = capsys.readouterr()

        # The format of the error message changes between python 3.9
        # and 3.10, so a full string comparison results in false
        # positive failures.  See https://bugs.python.org/issue41905
        # for more details
        assert captured.err.startswith(
            "error: Can't instantiate abstract class FabBuildTarget"
        )

    def test_valid_file(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Test with a simple valid build class."""

        target = tmp_path / "valid.py"

        target.write_text(
            dedent(
                """
                from fab.target.base import FabTargetBase
                class FabBuildTarget(FabTargetBase):
                  project_name = 'testing'
                  def run(self, args):
                    print("run method invoked")
                """
            )
        )

        fab.cui.__main__.main(["--file", str(target)])

        captured = capsys.readouterr()
        assert captured.out.startswith("run method invoked")
        assert captured.err == ""

    def test_default_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch
    ) -> None:
        """Test with a valid default file."""

        target = tmp_path / "FabFile"

        target.write_text(
            dedent(
                """
                from fab.target.base import FabTargetBase
                class FabBuildTarget(FabTargetBase):
                  project_name = 'testing'
                  def run(self, args):
                    print("run method invoked")
                """
            )
        )

        with monkeypatch.context() as mp:
            mp.chdir(tmp_path)
            fab.cui.__main__.main([])

        captured = capsys.readouterr()
        assert captured.out.startswith("run method invoked")
        assert captured.err == ""

    def test_interrupt_reporting(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Test the KeyboardInterrupt handling."""

        target = tmp_path / "valid.py"

        target.write_text(
            dedent(
                """
                from fab.target.base import FabTargetBase
                class FabBuildTarget(FabTargetBase):
                  project_name = 'testing'
                  def run(self, args):
                    raise KeyboardInterrupt()
                """
            )
        )

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", str(target)])

        assert exc.value.code == 11

        captured = capsys.readouterr()
        assert captured.err.startswith("error: interrupted by user")

    def test_invalid_import(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch
    ) -> None:
        """Test import failure error handling."""

        target = tmp_path / "valid.py"

        target.write_text(
            dedent(
                """
                def f():
                  return True
                """
            )
        )

        monkeypatch.setattr(fab.cui.__main__, "spec_from_loader", lambda a, b: None)

        with pytest.raises(SystemExit) as exc:
            fab.cui.__main__.main(["--file", str(target)])
        assert exc.value.code == 2

        captured = capsys.readouterr()

        assert "unable to import" in captured.err

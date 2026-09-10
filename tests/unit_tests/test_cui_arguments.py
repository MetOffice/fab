#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Tests for fab argument parser.
"""

import sys
import os
import argparse
from pathlib import Path
from fab.cui.arguments import full_path_type, FabArgumentParser

import pytest
from typing import Optional
from pyfakefs.fake_filesystem import FakeFilesystem
from unittest.mock import Mock


class TestFullPathType:
    """Tests for type which expands file paths."""

    def test_username(self):
        """Check username resolution."""

        assert str(full_path_type("~root")).startswith("/")

    def test_abspath(self):
        """Check relative paths become absolute."""

        assert str(full_path_type(".")).startswith("/")


class TestFabFile:
    """Check fab --file specific partial parsing."""

    def test_default(self, fs: FakeFilesystem):
        """Check default with no user arguments."""

        fs.create_file("FabFile")

        parser = FabArgumentParser()
        args = parser.parse_fabfile_only([])
        assert isinstance(args, argparse.Namespace)
        assert isinstance(args.file, Path)
        assert args.file.name == "FabFile"
        assert not args.zero_config

    @pytest.mark.parametrize(
        "filename,arg",
        [
            pytest.param(Path("FabFile"), None, id="default"),
            pytest.param(Path("myfile"), "myfile", id="override"),
        ],
    )
    def test_fabfile(
        self, filename: Path, arg: Optional[str], fs: FakeFilesystem
    ) -> None:
        """Check specified path with no user arguments."""

        fs.create_file(filename)

        parser = FabArgumentParser(fabfile=arg)
        args = parser.parse_fabfile_only([])
        assert isinstance(args, argparse.Namespace)
        assert isinstance(args.file, Path)
        assert args.file.name == filename.name
        assert not args.zero_config

    def test_nonexistent_default(self, fs: FakeFilesystem):
        """Check non-existent default file."""

        parser = FabArgumentParser()
        args = parser.parse_fabfile_only([])
        assert isinstance(args, argparse.Namespace)
        assert args.file is None
        assert args.zero_config

    def test_user_file(self, fs: FakeFilesystem):
        """Check user specified argument."""

        fs.create_file("myfile")

        parser = FabArgumentParser()
        args = parser.parse_fabfile_only(["--file", "myfile"])
        assert isinstance(args, argparse.Namespace)
        assert isinstance(args.file, Path)
        assert args.file.name == "myfile"
        assert not args.zero_config

    def test_nonexistent_user_file(self, fs: FakeFilesystem, capsys):
        """Check non-existent file with user specified argument."""

        parser = FabArgumentParser()

        with pytest.raises(SystemExit) as exc:
            parser.parse_fabfile_only(["--file", "myfile"])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "error: fab file does not exist" in captured.err

    def test_user_file_missing_arg(self, capsys):
        """Check missing file name triggers an error."""

        parser = FabArgumentParser()

        with pytest.raises(SystemExit) as exc:
            parser.parse_fabfile_only(["--file"])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "--file: expected one argument" in captured.err

    def test_no_help(self):
        """Check there the help option does nothing."""

        parser = FabArgumentParser()
        args = parser.parse_fabfile_only(["--help"])
        assert isinstance(args, argparse.Namespace)
        assert args.file is None

    def test_error_handling(self, monkeypatch):
        """Check the ArgumentError exception handling."""

        parser = FabArgumentParser()

        def replacement(*args, **kwargs):
            raise argparse.ArgumentError(
                Mock(option_strings=["--test"]), "error testing"
            )

        monkeypatch.setattr(argparse.ArgumentParser, "parse_known_args", replacement)

        args = parser.parse_fabfile_only([])
        assert isinstance(args, argparse.Namespace)
        assert args.file is None
        assert args.zero_config


class TestParser:
    """Test the core parser and its default options."""

    def test_defaults(self):
        """Default results with no arguments."""

        parser = FabArgumentParser()
        args = parser.parse_args([])

        assert isinstance(args, argparse.Namespace)
        assert args.file is None
        assert args.zero_config
        assert args.project is None
        assert isinstance(args.workspace, Path)
        assert args.workspace.name == "fab-workspace"
        assert args.debug is None
        assert args.verbose is None
        assert args.quiet is False

    def test_with_default_fabfile(self, fs: FakeFilesystem):
        """Defaults where a FabFile exists."""

        fs.create_file("FabFile")

        parser = FabArgumentParser()
        args = parser.parse_args([])

        assert isinstance(args, argparse.Namespace)
        assert isinstance(args.file, Path)
        assert args.file.name == "FabFile"
        assert not args.zero_config

    def test_with_alternate_fabfile(self, fs: FakeFilesystem):
        """Defaults with a non-default FabFile name."""

        fs.create_file("AltFabFile")

        parser = FabArgumentParser(fabfile="AltFabFile")
        args = parser.parse_args([])

        assert isinstance(args, argparse.Namespace)
        assert isinstance(args.file, Path)
        assert args.file.name == "AltFabFile"
        assert not args.zero_config

    @pytest.mark.parametrize(
        "argv,verbose,debug,quiet",
        [
            pytest.param(["-vv"], 2, None, False, id="verbose"),
            pytest.param(["-ddd"], None, 3, False, id="debug"),
            pytest.param(["-q"], None, None, True, id="quiet"),
            pytest.param(["-vv", "-ddd"], 2, 3, False, id="verbose+debug"),
        ],
    )
    def test_output(self, argv, verbose, debug, quiet):
        """Check combinations of output flags."""

        parser = FabArgumentParser()
        args = parser.parse_args(argv)

        assert args.verbose == verbose
        assert args.debug == debug
        assert args.quiet == quiet

    @pytest.mark.parametrize(
        "argv",
        [
            pytest.param(["-vv"], id="verbose"),
            pytest.param(["-ddd"], id="debug"),
            pytest.param(["-vv", "-ddd"], id="verbose+debug"),
        ],
    )
    def test_outupt_with_quiet(self, argv, capsys):
        """Check quiet and output options flag up an error."""

        parser = FabArgumentParser()

        with pytest.raises(SystemExit) as exc:
            parser.parse_args(argv + ["--quiet"])
        assert exc.value.code == 2

        captured = capsys.readouterr()
        assert "--quiet conflicts with debug and verbose settings" in captured.err

    @pytest.mark.parametrize(
        "argv,env,result",
        [
            pytest.param(
                [], None, Path("fab-workspace").expanduser().resolve(), id="default"
            ),
            pytest.param(
                [], Path("/tmp/fab"), Path("/tmp/fab").resolve(), id="environment"
            ),
            pytest.param(
                ["--workspace", "/run/fab"],
                Path("/tmp/fab"),
                Path("/run/fab").resolve(),
                id="argument",
            ),
        ],
    )
    def test_workspace(self, argv, env, result, monkeypatch):
        """Check various workspace settings."""

        parser = FabArgumentParser()

        if env is None and "FAB_WORKSPACE" in os.environ:
            monkeypatch.delenv("FAB_WORKSPACE")
        elif env is not None:
            monkeypatch.setenv("FAB_WORKSPACE", str(env))

        args = parser.parse_args(argv)

        assert args.workspace.name == result.name

    def test_partial_parse(self):
        """Check partial parse functionality."""

        parser = FabArgumentParser()
        args, rest = parser.parse_known_args(["--unknown"])

        assert hasattr(args, "zero_config")
        assert rest == ["--unknown"]

    def test_help(self, capsys):
        """Check default options are in help message."""

        parser = FabArgumentParser()

        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--help"])
        assert exc.value.code == 0

        captured = capsys.readouterr()

        assert "--file FILE" in captured.out
        assert "--project NAME" in captured.out
        assert "--workspace DIR" in captured.out
        assert "-d, --debug" in captured.out
        assert "-v, --verbose" in captured.out
        assert "-q, --quiet" in captured.out

    def test_alt_progname(self, monkeypatch):
        """Test alternate program naming scheme."""

        monkeypatch.setattr(sys, "argv", ["__main__.py"])

        parser = FabArgumentParser()
        args = parser.parse_args()

        assert parser.prog == "fab"
        assert args._progname == "fab"

        monkeypatch.setattr(os, "environ", {"__PROGNAME": "cui-test"})

        parser = FabArgumentParser()
        args = parser.parse_args()

        assert parser.prog == "cui-test"
        assert args._progname == "cui-test"

    def test_version(self, capsys, monkeypatch):

        monkeypatch.setattr(sys, "argv", ["__main__.py"])

        parser = FabArgumentParser()

        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--version"])
        assert exc.value.code == 0

        captured = capsys.readouterr()

        # Python 3.14 changes the behaviour, the output starts with
        # python -m pytest
        assert captured.out.startswith("fab ")

    def test_error_handling(self, monkeypatch):
        """Check the ArgumentError exception handling."""

        parser = FabArgumentParser()

        def replacement(*args, **kwargs):
            return None, None

        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", replacement)

        with pytest.raises(ValueError) as exc:
            parser.parse_args(["--version"])
        assert "invalid return value from wrapped function" in str(exc.value)


class TestCompilerFlags:
    """Test the compiler target flags."""

    def test_defaults(self, monkeypatch):
        """Test class default settings."""

        if "CC" in os.environ:
            monkeypatch.delenv("CC")
        if "CXX" in os.environ:
            monkeypatch.delenv("CXX")
        if "FC" in os.environ:
            monkeypatch.delenv("FC")

        parser = FabArgumentParser()
        args = parser.parse_args([])

        assert args.cc == "gcc"
        assert args.cxx == "g++"
        assert args.fc == "gfortran"

    @pytest.mark.parametrize(
        "argv,env,cc,cxx,fc",
        [
            pytest.param(["--cc", "icc"], {}, "icc", "g++", "gfortran", id="cc flag"),
            pytest.param(["--cxx", "icx"], {}, "gcc", "icx", "gfortran", id="cxx flag"),
            pytest.param(["--fc", "ifx"], {}, "gcc", "g++", "ifx", id="fc flag"),
            pytest.param([], {"CC": "icc"}, "icc", "g++", "gfortran", id="CC env"),
            pytest.param([], {"CXX": "icx"}, "gcc", "icx", "gfortran", id="CXX env"),
            pytest.param([], {"FC": "ifx"}, "gcc", "g++", "ifx", id="FC env"),
            pytest.param(
                ["--cc", "cc"],
                {"CC": "icc"},
                "cc",
                "g++",
                "gfortran",
                id="cc flag+env",
            ),
            pytest.param(
                ["--cxx", "CC"],
                {"CXX": "icc"},
                "gcc",
                "CC",
                "gfortran",
                id="cxx flag+env",
            ),
            pytest.param(
                ["--fc", "ftn"],
                {"FC": "ifx"},
                "gcc",
                "g++",
                "ftn",
                id="FC flag+env",
            ),
        ],
    )
    def test_from_env(self, argv, env, cc, cxx, fc, monkeypatch):
        """Check compiler settings and environment overrides."""

        for key, value in env.items():
            monkeypatch.setenv(key, value)

        parser = FabArgumentParser()
        args = parser.parse_args(argv)

        assert args.cc == cc
        assert args.cxx == cxx
        assert args.fc == fc

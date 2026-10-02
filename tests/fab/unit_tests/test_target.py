#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Unit tests for fab recipe classes.
"""

import argparse
import pytest

from fab.target.base import FabTargetBase
from fab.target.zero import FabZeroConfig


def test_valid_subclass():
    """Create a valid subclass from FabTargetBase."""

    class FabTarget(FabTargetBase):
        """Trivial test class."""

        project_name = "test-class"

        def run(self, _):
            """Dummy run method."""

    assert issubclass(FabTarget, FabTargetBase)

    target = FabTarget()
    assert isinstance(target, FabTargetBase)


def test_invalid_subclasses():
    """Create invalid subclasses from FabTargetBase."""

    class FabInvalidMethod(FabTargetBase):
        """Missing abstract methods."""

        project_name = "test-class"

    with pytest.raises(TypeError) as exc:
        _ = FabInvalidMethod()
    assert "Can't instantiate abstract class" in str(exc)

    class FabInvalidProject(FabTargetBase):
        """Missing project_name property."""

        def run(self, _):
            """Dummy run method."""

    with pytest.raises(TypeError) as exc:
        _ = FabInvalidMethod()
    assert "Can't instantiate abstract class" in str(exc)


def test_add_arguments():
    """Test add_arguments static method."""

    class FabTargetArgs(FabTargetBase):
        """Test class with add_arguments."""

        @staticmethod
        def add_arguments(p):
            """Add a positional argument."""
            p.add_argument("test", type=str)

    parser = argparse.ArgumentParser()
    FabTargetArgs.add_arguments(parser)
    args = parser.parse_args(["abc"])

    assert isinstance(args, argparse.Namespace)
    assert args.test == "abc"


def test_zero_config(tmp_path):
    """Test the zero config target class."""

    # Create a trivial bit of fortran
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    work = tmp_path / "fab-workspace"
    work.mkdir()

    with open(src_dir / "test.f90", "w", encoding="utf-8") as fd:
        print("program test\nwrite(*,*) 'testcase'\nend program test", file=fd)

    zero = FabZeroConfig()
    assert isinstance(zero, FabTargetBase)

    zero.run(
        argparse.Namespace(
            source=src_dir,
            workspace=work,
        )
    )

    # Check the project directory to ensure that the zero config
    # class has run correctly
    project = work / "zero-config"

    assert project.is_dir()
    assert (project / "source").is_dir()
    assert (project / "source" / "test.f90").is_file()
    assert (project / "test").is_file()

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests tooling base classes.
"""
import logging
from pathlib import Path

from fab.tools.category import Category
from fab.tools.compiler_suite_tool import CompilerSuiteTool


def test_compiler_suite_toolconstructor() -> None:
    """
    Tests construction from argument list.
    """
    tool = CompilerSuiteTool(name="gfortran", exec_name="gfortran",
                             suite="gnu", category=Category.FORTRAN_COMPILER)
    assert tool.suite == "gnu"
    assert str(tool) == "CompilerSuiteTool - gfortran: gfortran"
    assert tool.exec_name == "gfortran"
    assert tool.exec_path == Path("gfortran")
    assert tool.name == "gfortran"
    assert tool.category == Category.FORTRAN_COMPILER
    assert isinstance(tool.logger, logging.Logger)
    assert tool.is_compiler

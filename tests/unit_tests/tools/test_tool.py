##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the tool infrastructure.
"""
import logging
from pathlib import Path
from unittest import mock

import pytest

from fab import FabException
from fab.tools import Category, CompilerSuiteTool, Tool


def test_tool_constructor():
    '''Test the constructor.'''
    tool = Tool("gnu", "gfortran", Category.FORTRAN_COMPILER)
    assert str(tool) == "Tool - gnu: gfortran"
    assert tool.exec_name == "gfortran"
    assert tool.name == "gnu"
    assert tool.category == Category.FORTRAN_COMPILER
    assert isinstance(tool.logger, logging.Logger)
    assert tool.is_compiler

    linker = Tool("gnu", "gfortran", Category.LINKER)
    assert str(linker) == "Tool - gnu: gfortran"
    assert linker.exec_name == "gfortran"
    assert linker.name == "gnu"
    assert linker.category == Category.LINKER
    assert isinstance(linker.logger, logging.Logger)
    assert not linker.is_compiler

    # Check that a path is accepted
    mytool = Tool("MyTool", Path("/bin/mytool"))
    assert mytool.name == "MyTool"
    # A path should be converted to a string, since this
    # is later passed to the subprocess command
    assert mytool.exec_name == "/bin/mytool"
    assert mytool.category == Category.MISC

    # Check that if we specify no category, we get the default:
    misc = Tool("misc", "misc")
    assert misc.exec_name == "misc"
    assert misc.name == "misc"
    assert misc.category == Category.MISC


def test_tool_is_available():
    '''Test that is_available works as expected.'''
    tool = Tool("gfortran", "gfortran", Category.FORTRAN_COMPILER)
    with mock.patch.object(tool, "check_available", return_value=True):
        assert tool.is_available
    # Test the getter
    tool._is_available = False
    assert not tool.is_available
    assert tool.is_compiler

    # Test the exception when trying to use in a non-existent tool:
    with pytest.raises(FabException) as err:
        tool.run("--ops")
    assert ("Tool 'gfortran' is not available to run '['gfortran', '--ops']'"
            in str(err.value))


class TestToolRun:
    '''Test the run method of Tool.'''

    def test_no_error_no_args(self,):
        '''Test usage of `run` without any errors when no additional
        command line argument is provided.'''
        tool = Tool("gnu", "gfortran", Category.FORTRAN_COMPILER)
        mock_result = mock.Mock(returncode=0, return_value=123)
        mock_result.stdout.decode = mock.Mock(return_value="123")

        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result):
            assert tool.run(capture_output=True) == "123"
            assert tool.run(capture_output=False) == ""

    def test_no_error_with_single_args(self):
        '''Test usage of `run` without any errors when a single
        command line argument is provided as string.'''
        tool = Tool("gnu", "gfortran", Category.FORTRAN_COMPILER)
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            tool.run("a")
        tool_run.assert_called_once_with(
            ["gfortran", "a"], capture_output=True, env=None,
            cwd=None, check=False)

    def test_no_error_with_multiple_args(self):
        '''Test usage of `run` without any errors when more than
        one command line argument is provided as a list.'''
        tool = Tool("gnu", "gfortran", Category.FORTRAN_COMPILER)
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            tool.run(["a", "b"])
        tool_run.assert_called_once_with(
            ["gfortran", "a", "b"], capture_output=True, env=None,
            cwd=None, check=False)

    def test_error(self):
        '''Tests the error handling of `run`. '''
        tool = Tool("gnu", "gfortran", Category.FORTRAN_COMPILER)
        result = mock.Mock(returncode=1)
        mocked_error_message = 'mocked error message'
        result.stderr.decode = mock.Mock(return_value=mocked_error_message)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=result):
            with pytest.raises(FabException) as err:
                tool.run()
            assert mocked_error_message in str(err.value)
            assert "Command failed with return code 1" in str(err.value)

    def test_error_file_not_found(self):
        '''Tests the error handling of `run`. '''
        tool = Tool("does_not_exist", "does_not_exist",
                    Category.FORTRAN_COMPILER)
        with mock.patch('fab.tools.tool.subprocess.run',
                        side_effect=FileNotFoundError("not found")):
            with pytest.raises(FabException) as err:
                tool.run()
            assert ("Command '['does_not_exist']' could not be executed."
                    in str(err.value))


def test_suite_tool():
    '''Test the constructor.'''
    tool = CompilerSuiteTool("gnu", "gfortran", "gnu",
                             Category.FORTRAN_COMPILER)
    assert str(tool) == "CompilerSuiteTool - gnu: gfortran"
    assert tool.exec_name == "gfortran"
    assert tool.name == "gnu"
    assert tool.suite == "gnu"
    assert tool.category == Category.FORTRAN_COMPILER
    assert isinstance(tool.logger, logging.Logger)

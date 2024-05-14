##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the tool class.
'''


import logging
from pathlib import Path

from unittest import mock

from fab.tools import (Categories, Cpp, CppFortran, Fpp, Preprocessor)


def test_preprocessor_constructor():
    '''Test the constructor.'''
    tool = Preprocessor("cpp-fortran", "cpp", Categories.FORTRAN_PREPROCESSOR)
    assert str(tool) == "Preprocessor - cpp-fortran: cpp"
    assert tool.exec_name == "cpp"
    assert tool.name == "cpp-fortran"
    assert tool.category == Categories.FORTRAN_PREPROCESSOR
    assert isinstance(tool.logger, logging.Logger)


def test_preprocessor_fpp_is_available():
    '''Test that is_available works as expected.'''
    fpp = Fpp()
    mock_run = mock.Mock(side_effect=RuntimeError("not found"))
    with mock.patch("subprocess.run", mock_run):
        assert not fpp.is_available

    # Reset the flag and pretend run returns a success:
    fpp._is_available = None
    mock_run = mock.Mock(returncode=0)
    with mock.patch("fab.tools.tool.Tool.run", mock_run):
        assert fpp.is_available


def test_preprocessor_cpp():
    '''Test cpp.'''
    cpp = Cpp()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        cpp.run("--version")
    tool_run.assert_called_with(["cpp", "--version"], capture_output=True,
                                env=None, cwd=None, check=False)

    # Reset the flag and raise an error when executing:
    cpp._is_available = None
    mock_run = mock.Mock(side_effect=RuntimeError("not found"))
    with mock.patch("fab.tools.tool.Tool.run", mock_run):
        assert not cpp.is_available


def test_preprocessor_cppfortran():
    '''Test cpp for Fortran, which adds additional command line options in.'''
    cppf = CppFortran()
    assert cppf.is_available
    # First create a mock object that is the result of subprocess.run.
    # Tool will only check `returncode` of this object.
    mock_result = mock.Mock(returncode=0)
    # Then set this result as result of a mock run function
    mock_run = mock.Mock(return_value=mock_result)

    with mock.patch("subprocess.run", mock_run):
        # First test calling without additional flags:
        cppf.preprocess(Path("a.in"), Path("a.out"))
    mock_run.assert_called_with(
        ["cpp", "-traditional-cpp", "-P", "a.in", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)

    with mock.patch("subprocess.run", mock_run):
        # Then test with added flags:
        cppf.preprocess(Path("a.in"), Path("a.out"), ["-DDO_SOMETHING"])
    mock_run.assert_called_with(
        ["cpp", "-traditional-cpp", "-P", "-DDO_SOMETHING", "a.in", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)

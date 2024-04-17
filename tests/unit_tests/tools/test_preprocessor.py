##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the tool class.
'''


import logging

from unittest import mock

# TODO: why is ignore required?
from fab.newtools import (Categories, Cpp, CppFortran, Fpp,   # type: ignore
                          Preprocessor)


def test_preprocessor_constructor():
    '''Test the constructor.'''
    tool = Preprocessor("cpp-fortran", "cpp", Categories.FORTRAN_PREPROCESSOR)
    assert str(tool) == "Preprocessor - cpp-fortran: cpp"
    assert tool.exec_name == "cpp"
    assert tool.name == "cpp-fortran"
    assert tool.category == Categories.FORTRAN_PREPROCESSOR
    assert isinstance(tool.logger, logging.Logger)


def test_preprocessor_is_available():
    '''Test that is_available works as expected.'''
    fpp = Fpp()
    assert not fpp.is_available


def test_preprocessor_cpp():
    '''Test cpp.'''
    cpp = Cpp()
    assert cpp.is_available
    # First create a mock object that is the result of subprocess.run.
    # Tool will only check `returncode` of this object.
    mock_result = mock.Mock(returncode=0)
    # Then set this result as result of a mock run function
    mock_run = mock.Mock(return_value=mock_result)

    with mock.patch("subprocess.run", mock_run):
        cpp.run("--version")
        mock_run.assert_called_with(["cpp", "--version"], capture_output=True,
                                    env=None, cwd=None, check=False)


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
        cppf.run("--version")
        mock_run.assert_called_with(["cpp", "-traditional-cpp", "-P",
                                     "--version"],
                                    capture_output=True, env=None, cwd=None,
                                    check=False)

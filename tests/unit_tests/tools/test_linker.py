##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the linker implementation.
'''

from pathlib import Path
from unittest import mock

import pytest

from fab.tools import (Category, Linker)


def test_linker(mock_c_compiler, mock_fortran_compiler):
    '''Test the linker constructor.'''

    linker = Linker(name="my_linker", exec_name="my_linker.exe",
                    suite="suite")
    assert linker.category == Category.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == "my_linker.exe"
    assert linker.suite == "suite"
    assert linker.flags == []

    linker = Linker(name="my_linker", compiler=mock_c_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.suite == mock_c_compiler.suite
    assert linker.flags == []

    linker = Linker(compiler=mock_c_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == mock_c_compiler.name
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.suite == mock_c_compiler.suite
    assert linker.flags == []

    linker = Linker(compiler=mock_fortran_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == mock_fortran_compiler.name
    assert linker.exec_name == mock_fortran_compiler.exec_name
    assert linker.flags == []

    with pytest.raises(RuntimeError) as err:
        linker = Linker(name="no-exec-given")
    assert ("Either specify name, exec name, and suite or a compiler when "
            "creating Linker." in str(err.value))


def test_linker_check_available(mock_c_compiler):
    '''Tests the is_available functionality.'''

    # First test if a compiler is given. The linker will call the
    # corresponding function in the compiler:
    linker = Linker(compiler=mock_c_compiler)
    with mock.patch.object(mock_c_compiler, "check_available",
                           return_value=True) as comp_run:
        assert linker.check_available()
    # It should be called once without any parameter
    comp_run.assert_called_once_with()

    # Second test, no compiler is given. Mock Tool.run to
    # return a success:
    linker = Linker("ld", "ld", suite="gnu")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.check_available()
    tool_run.assert_called_once_with(
        ["ld", "--version"], capture_output=True, env=None,
        cwd=None, check=False)

    # Third test: assume the tool does not exist, check_available
    # will return False (and not raise  an exception)
    linker._is_available = None
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        assert linker.check_available() is False


def test_linker_c(mock_c_compiler):
    '''Test the link command line when no additional libraries are
    specified.'''
    linker = Linker(compiler=mock_c_compiler)
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ["mock_c_compiler.exe", 'a.o', '-o', 'a.out'], capture_output=True,
        env=None, cwd=None, check=False)


def test_linker_c_with_libraries(mock_c_compiler):
    '''Test the link command line when additional libraries are specified.'''
    linker = Linker(compiler=mock_c_compiler)
    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"), add_libs=["-L", "/tmp"],
                    openmp=True)
    link_run.assert_called_with(['-fopenmp', 'a.o', '-L', '/tmp',
                                 '-o', 'a.out'])


def test_compiler_linker_add_compiler_flag(mock_c_compiler):
    '''Test that a flag added to the compiler will be automatically
    added to the link line (even if the flags are modified after
    creating the linker ... in case that the user specifies additional
    flags after creating the linker).'''

    linker = Linker(compiler=mock_c_compiler)
    mock_c_compiler.flags.append("-my-flag")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ['mock_c_compiler.exe', '-my-flag', 'a.o', '-o', 'a.out'],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_add_compiler_flag():
    '''Make sure linker flags work if a linker is created without
    a compiler:
    '''
    linker = Linker("no-compiler", "no-compiler.exe", "suite")
    linker.flags.append("-some-other-flag")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ['no-compiler.exe', '-some-other-flag', 'a.o', '-o', 'a.out'],
        capture_output=True, env=None, cwd=None, check=False)

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

from fab.newtools import (Categories, Linker)


def test_linker(mock_c_compiler, mock_fortran_compiler):
    '''Test the linker constructor.'''

    linker = Linker(name="my_linker", exec_name="my_linker.exe",
                    vendor="vendor")
    assert linker.category == Categories.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == "my_linker.exe"
    assert linker.vendor == "vendor"
    assert linker.flags == []

    linker = Linker(name="my_linker", compiler=mock_c_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.vendor == mock_c_compiler.vendor
    assert linker.flags == []

    linker = Linker(compiler=mock_c_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == mock_c_compiler.name
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.vendor == mock_c_compiler.vendor
    assert linker.flags == []

    linker = Linker(compiler=mock_fortran_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == mock_fortran_compiler.name
    assert linker.exec_name == mock_fortran_compiler.exec_name
    assert linker.flags == []

    with pytest.raises(RuntimeError) as err:
        linker = Linker(name="no-exec-given")
    assert ("Either specify name, exec name, and vendor or a compiler when "
            "creating Linker." in str(err.value))


def test_linker_c(mock_c_compiler):
    '''Test the link command line.'''
    linker = Linker(compiler=mock_c_compiler)
    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"))
    link_run.assert_called_with(['a.o', '-o', 'a.out'])

    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"), add_libs=["-L", "/tmp"])
    link_run.assert_called_with(['a.o', '-L', '/tmp', '-o', 'a.out'])


def test_linker_add_compiler_flag(mock_c_compiler):
    '''Test that a flag added to the compiler will be automatically
    added to the link line (even if the flags are modified after
    creating the linker ... in case that the user specifies additional
    flags after creating the linker).'''

    linker = Linker(compiler=mock_c_compiler)
    mock_c_compiler.flags.append("-my-flag")
    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"))
    link_run.assert_called_with(['-my-flag', 'a.o', '-o', 'a.out'])

    # Make also sure the code works if a linker is created without
    # a compiler:
    linker = Linker("no-compiler", "no-compiler.exe", "vendor")
    linker.flags.append("-some-other-flag")
    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"))
    link_run.assert_called_with(['a.o', '-some-other-flag', '-o', 'a.out'])

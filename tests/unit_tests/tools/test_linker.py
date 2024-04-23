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


def test_compiler(mock_c_compiler, mock_fortran_compiler):
    '''Test the linker constructor.'''

    linker = Linker(name="my_linker", exec_name="my_linker.exe")
    assert linker.category == Categories.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == "my_linker.exe"
    assert linker.flags == []

    linker = Linker(name="my_linker", compiler=mock_c_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == "my_linker"
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.flags == []

    linker = Linker(compiler=mock_c_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == mock_c_compiler.name
    assert linker.exec_name == mock_c_compiler.exec_name
    assert linker.flags == []

    linker = Linker(compiler=mock_fortran_compiler)
    assert linker.category == Categories.LINKER
    assert linker.name == mock_fortran_compiler.name
    assert linker.exec_name == mock_fortran_compiler.exec_name
    assert linker.flags == []

    with pytest.raises(RuntimeError) as err:
        linker = Linker(name="no-exec-given")
    assert ("Either specify name and exec name, or a compiler when creating "
            "Linker." in str(err.value))


def test_link_c(mock_c_compiler):
    '''Test the link command line.'''
    linker = Linker(compiler=mock_c_compiler)
    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"))
    link_run.assert_called_with(['a.o', '-o', 'a.out'])

    with mock.patch.object(linker, "run") as link_run:
        linker.link([Path("a.o")], Path("a.out"), add_libs=["-L", "/tmp"])
    link_run.assert_called_with(['a.o', '-L', '/tmp', '-o', 'a.out'])

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the ToolRepository.
'''

import pytest

from fab.newtools import (Gcc, Gfortran, Ifort, ToolRepository)


def test_tool_repository_constructor():
    '''Tests the ToolRepository constructor.'''
    tr = ToolRepository()
    assert tr.C_COMPILER in tr
    assert tr.FORTRAN_COMPILER in tr


def test_tool_repository_get_tool():
    '''Tests get_tool.'''
    tr = ToolRepository()
    gfortran = tr.get_tool(tr.FORTRAN_COMPILER, "gfortran")
    assert isinstance(gfortran, Gfortran)

    ifort = tr.get_tool(tr.FORTRAN_COMPILER, "ifort")
    assert isinstance(ifort, Ifort)


def test_tool_repository_get_tool_error():
    '''Tests error handling during tet_tool.'''
    tr = ToolRepository()
    with pytest.raises(KeyError) as err:
        tr.get_tool("unknown-category", "something")
    assert "Unknown category 'unknown-category'" in str(err.value)

    with pytest.raises(KeyError) as err:
        tr.get_tool(tr.C_COMPILER, "something")
    assert ("Unknown tool 'something' in category 'c-compiler'"
            in str(err.value))


def test_tool_repository_get_default():
    '''Tests get_default.'''
    tr = ToolRepository()
    gfortran = tr.get_default("fortran-compiler")
    assert isinstance(gfortran, Gfortran)

    gcc = tr.get_default("c-compiler")
    assert isinstance(gcc, Gcc)


def test_tool_repository_get_default_error():
    '''Tests error handling in get_default.'''
    tr = ToolRepository()
    with pytest.raises(KeyError) as err:
        tr.get_default("unknown-category")
    assert "Unknown category 'unknown-category'" in str(err.value)

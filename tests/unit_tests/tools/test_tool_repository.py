##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the ToolRepository.
'''

import pytest

# TODO I don't know why mypy complains here
# $ mypy  ./test_tool_repository.py
# test_tool_repository.py:14: error: Skipping analyzing "fab.newtools":
#     module is installed, but missing library stubs or py.typed marker
#     [import-untyped]
# test_tool_repository.py:14: note: See https://mypy.readthedocs.io/en/stable
#     /running_mypy.html#missing-imports
# test_tool_repository.py:35: note: By default the bodies of untyped functions
# are not checked, consider using --check-untyped-defs  [annotation-unchecked]

from fab.newtools import (Categories, Gcc, Gfortran, Ifort,
                          ToolRepository)  # type: ignore


def test_tool_repository_get_singleton():
    '''Tests the singleton behaviour.'''
    ToolRepository._singleton = None
    with pytest.raises(RuntimeError) as err:
        ToolRepository()
    assert ("You must use 'ToolRepository.get()' to get the singleton "
            "instance." in str(err.value))
    tr1 = ToolRepository.get()
    tr2 = ToolRepository.get()
    assert tr1 is tr2

    ToolRepository._singleton = None
    tr3 = ToolRepository.get()
    assert tr1 is not tr3


def test_tool_repository_constructor():
    '''Tests the ToolRepository constructor.'''
    tr = ToolRepository.get()
    assert Categories.C_COMPILER in tr
    assert Categories.FORTRAN_COMPILER in tr


def test_tool_repository_get_tool():
    '''Tests get_tool.'''
    tr = ToolRepository.get()
    gfortran = tr.get_tool(Categories.FORTRAN_COMPILER, "gfortran")
    assert isinstance(gfortran, Gfortran)

    ifort = tr.get_tool(Categories.FORTRAN_COMPILER, "ifort")
    assert isinstance(ifort, Ifort)


def test_tool_repository_get_tool_error():
    '''Tests error handling during tet_tool.'''
    tr = ToolRepository.get()
    with pytest.raises(KeyError) as err:
        tr.get_tool("unknown-category", "something")
    assert "Unknown category 'unknown-category'" in str(err.value)

    with pytest.raises(KeyError) as err:
        tr.get_tool(Categories.C_COMPILER, "something")
    assert ("Unknown tool 'something' in category 'C_COMPILER'"
            in str(err.value))


def test_tool_repository_get_default():
    '''Tests get_default.'''
    tr = ToolRepository.get()
    gfortran = tr.get_default(Categories.FORTRAN_COMPILER)
    assert isinstance(gfortran, Gfortran)

    gcc = tr.get_default(Categories.C_COMPILER)
    assert isinstance(gcc, Gcc)


def test_tool_repository_get_default_error():
    '''Tests error handling in get_default.'''
    tr = ToolRepository.get()
    with pytest.raises(RuntimeError) as err:
        tr.get_default("unknown-category")
    assert "Invalid category type 'str'." in str(err.value)

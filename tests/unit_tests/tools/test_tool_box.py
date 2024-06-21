##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the TooBox class.
'''
from unittest import mock
import warnings

import pytest

from fab.tools import Category, CCompiler, Gfortran, ToolBox, ToolRepository


def test_tool_box_constructor():
    '''Tests the ToolBox constructor.'''
    tb = ToolBox()
    assert isinstance(tb._all_tools, dict)


def test_tool_box_get_tool():
    '''Tests get_tool.'''
    tb = ToolBox()
    # No tool is defined, so the default Fortran compiler must be returned:
    default_compiler = tb.get_tool(Category.FORTRAN_COMPILER)
    tr = ToolRepository()
    assert default_compiler is tr.get_default(Category.FORTRAN_COMPILER)
    # Check that dictionary-like access works as expected:
    assert tb[Category.FORTRAN_COMPILER] == default_compiler

    # Now add gfortran as Fortran compiler to the tool box
    tr_gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")
    tb.add_tool(tr_gfortran)
    gfortran = tb.get_tool(Category.FORTRAN_COMPILER)
    assert gfortran is tr_gfortran


def test_tool_box_add_tool_replacement():
    '''Test that replacing a tool raises a warning, and that this
    warning can be disabled.'''

    tb = ToolBox()
    mock_compiler1 = CCompiler("mock_c_compiler1", "mock_exec1", "suite")
    mock_compiler1._is_available = True
    mock_compiler2 = CCompiler("mock_c_compiler2", "mock_exec2", "suite")
    mock_compiler2._is_available = True

    tb.add_tool(mock_compiler1)

    warn_message = (f"Replacing existing tool '{mock_compiler1}' with "
                    f"'{mock_compiler2}'.")
    with pytest.warns(UserWarning, match=warn_message):
        tb.add_tool(mock_compiler2)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tb.add_tool(mock_compiler1, silent_replace=True)


def test_tool_box_add_tool_not_avail():
    '''Test that tools that are not available cannot be added to
    a tool box.'''

    tb = ToolBox()
    gfortran = Gfortran()
    # Mark this compiler to be not available:
    with mock.patch.object(gfortran, "check_available", return_value=False):
        with pytest.raises(RuntimeError) as err:
            tb.add_tool(gfortran)
        assert f"Tool '{gfortran}' is not available" in str(err.value)

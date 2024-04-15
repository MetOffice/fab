##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This module tests the TooBox class.
'''

from fab.newtools import Categories, ToolBox, ToolRepository


def test_tool_box_constructor():
    '''Tests the ToolBox constructor.'''
    tb = ToolBox()
    assert isinstance(tb._all_tools, dict)


def test_tool_box_get_tool():
    '''Tests get_tool.'''
    tb = ToolBox()
    tr = ToolRepository.get()
    default_compiler = tb.get_tool(Categories.FORTRAN_COMPILER)
    assert default_compiler is tr.get_default(Categories.FORTRAN_COMPILER)

    tr_gfortran = tr.get_tool(Categories.FORTRAN_COMPILER, "gfortran")
    tb.add_tool(Categories.FORTRAN_COMPILER, tr_gfortran)
    gfortran = tb.get_tool(Categories.FORTRAN_COMPILER)
    assert gfortran is tr_gfortran

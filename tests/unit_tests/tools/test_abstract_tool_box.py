##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the AbstractToolBox class.
"""

from typing import Optional

import pytest

from fab.tools.abstract_tool_box import AbstractToolBox
from fab.tools.category import Category
from fab.tools.compiler import Gfortran
from fab.tools.tool import Tool


def test_is_abstract():
    """
    Test that the abstract class cannot be instantiated.
    """
    with pytest.raises(TypeError) as err:
        # pylint: disable=abstract-class-instantiated
        AbstractToolBox()
    assert "Can't instantiate abstract class AbstractToolBox" in str(err.value)


def test_derived():
    """
    Tests that we can create a derived class that can be instantiated.
    """
    class DummyToolBox(AbstractToolBox):
        """
        A dummy class to check that we can derive and instantiate from
        the AbstractToolBox.
        """

        def __getitem__(self, category: Category) -> Tool:
            return Gfortran()

        def add_tool(self, tool: Tool,
                     silent_replace: bool = False) -> None:
            pass

        def get_tool(self, category: Category,
                     mpi: Optional[bool] = None,
                     openmp: Optional[bool] = None,
                     enforce_fortran_linker: Optional[bool] = None) -> Tool:
            return Gfortran()

        def has(self, category: Category) -> bool:
            return False

    dtb = DummyToolBox()
    assert isinstance(dtb, AbstractToolBox)
    assert isinstance(dtb, DummyToolBox)

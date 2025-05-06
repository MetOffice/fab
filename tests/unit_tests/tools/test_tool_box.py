##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests holding tools in a tool box.
"""
import warnings

from pytest import raises, warns
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import not_found_callback

from fab.tools.category import Category
from fab.tools.compiler import CCompiler, Gfortran
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository


def test_constructor() -> None:
    """
    Tests the default constructor.

    ToDo: routing around in private state is bad.
    """
    tb = ToolBox()
    assert isinstance(tb._all_tools, dict)


def test_add_get_tool() -> None:
    """
    Tests adding and retrieving tools.

    ToDo: There seems to be a lot of collusion between objects. Is there a
          looser way to couple this stuff?
    """
    tb = ToolBox()
    # No tool is defined, so the default Fortran compiler must be returned:
    default_compiler = tb.get_tool(Category.FORTRAN_COMPILER,
                                   mpi=False, openmp=False)
    tr = ToolRepository()
    assert default_compiler is tr.get_default(Category.FORTRAN_COMPILER,
                                              mpi=False, openmp=False)
    # Check that dictionary-like access works as expected:
    assert tb[Category.FORTRAN_COMPILER] == default_compiler

    # Now add gfortran as Fortran compiler to the tool box
    tr_gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")
    tb.add_tool(tr_gfortran, silent_replace=True)
    gfortran = tb.get_tool(Category.FORTRAN_COMPILER)
    assert gfortran is tr_gfortran


def test_tool_replacement() -> None:
    """
    Tests tool replacement functionality.
    """
    tb = ToolBox()
    mock_compiler1 = CCompiler("mock_c_compiler1", "mock_exec1", "suite",
                               version_regex="something")
    mock_compiler1._is_available = True
    mock_compiler2 = CCompiler("mock_c_compiler2", "mock_exec2", "suite",
                               version_regex="something")
    mock_compiler2._is_available = True

    tb.add_tool(mock_compiler1)

    warn_message = (f"Replacing existing tool '{mock_compiler1}' with "
                    f"'{mock_compiler2}'.")
    with warns(UserWarning, match=warn_message):
        tb.add_tool(mock_compiler2)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tb.add_tool(mock_compiler1, silent_replace=True)


def test_add_unavailable_tool(fake_process: FakeProcess) -> None:
    """
    Tests unavailable tools are not accepted by toolbox.
    """
    fake_process.register(['gfortran', '--version'],
                          callback=not_found_callback)

    tb = ToolBox()
    gfortran = Gfortran()
    with raises(RuntimeError) as err:
        tb.add_tool(gfortran)
    assert str(err.value).startswith(f"Tool '{gfortran}' is not available")

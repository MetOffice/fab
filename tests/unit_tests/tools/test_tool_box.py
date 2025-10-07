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
from fab.tools.compiler import CCompiler, FortranCompiler, Gfortran
from fab.tools.tool_box import ToolBox


def test_constructor() -> None:
    """
    Tests the default constructor.

    ToDo: routing around in private state is bad.
    """
    tb = ToolBox()
    assert isinstance(tb._all_tools, dict)


def test_add_get_tool(stub_tool_repository) -> None:
    """
    Tests adding and retrieving tools.

    ToDo: There seems to be a lot of collusion between objects. Is there a
          looser way to couple this stuff?
    """

    tb = ToolBox()
    # No tool is defined, so the default Fortran compiler from the
    # ToolRepository must be returned:
    default_compiler = tb.get_tool(Category.FORTRAN_COMPILER,
                                   mpi=False, openmp=False)
    assert (default_compiler is
            stub_tool_repository.get_default(Category.FORTRAN_COMPILER,
                                             mpi=False, openmp=False))
    # Check that dictionary-like access works as expected:
    assert tb[Category.FORTRAN_COMPILER] == default_compiler

    # Now add a new Fortran compiler to the tool box
    new_fc = FortranCompiler('new Fortran compiler', 'nfc', 'new',
                             r'([\d.]+)', openmp_flag='-omp',
                             module_folder_flag='-mods')
    new_fc._is_available = True

    tb.add_tool(new_fc, silent_replace=True)

    # Now we must not get the default compiler anymore, but the newly
    # added compiler instead:
    tb_fc = tb.get_tool(Category.FORTRAN_COMPILER, mpi=False, openmp=False)
    assert tb_fc is new_fc


def test_has(stub_fortran_compiler) -> None:
    """
    Tests checking if a tool is specified in a tool box or not.
    """
    tb = ToolBox()

    assert tb.has(Category.FORTRAN_COMPILER) is False
    stub_fortran_compiler._is_available = True
    tb.add_tool(stub_fortran_compiler)
    assert tb.has(Category.FORTRAN_COMPILER) is True


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

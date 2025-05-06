##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests ToolBox class.
"""
from pytest import mark, raises
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import ExtendedRecorder

from fab.tools.ar import Ar
from fab.tools.category import Category
from fab.tools.compiler import Gcc, Gfortran, FortranCompiler, Ifort
from fab.tools.tool_repository import ToolRepository


def test_tool_repository_get_singleton_new():
    '''Tests the singleton behaviour.'''
    ToolRepository._singleton = None
    tr1 = ToolRepository()
    tr2 = ToolRepository()
    assert tr1 == tr2
    ToolRepository._singleton = None
    tr3 = ToolRepository()
    assert tr1 is not tr3


def test_tool_repository_constructor():
    '''Tests the ToolRepository constructor.'''
    tr = ToolRepository()
    assert Category.C_COMPILER in tr
    assert Category.FORTRAN_COMPILER in tr


def test_tool_repository_get_tool():
    '''Tests get_tool.'''
    tr = ToolRepository()
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")
    assert isinstance(gfortran, Gfortran)

    ifort = tr.get_tool(Category.FORTRAN_COMPILER, "ifort")
    assert isinstance(ifort, Ifort)


def test_get_tool_error():
    """
    Tests error handling during tet_tool.
    """
    tr = ToolRepository()
    with raises(KeyError) as err:
        tr.get_tool("unknown-category", "something")
    assert "Unknown category 'unknown-category'" in str(err.value)

    with raises(KeyError) as err:
        tr.get_tool(Category.C_COMPILER, "something")
    assert ("Unknown tool 'something' in category 'C_COMPILER'"
            in str(err.value))


def test_get_default() -> None:
    '''Tests get_default.'''
    tr = ToolRepository()
    gfortran = tr.get_default(Category.FORTRAN_COMPILER, mpi=False,
                              openmp=False)
    assert isinstance(gfortran, Gfortran)

    gcc = tr.get_default(Category.C_COMPILER, mpi=False, openmp=False)
    assert isinstance(gcc, Gcc)

    # Test a non-compiler
    ar = tr.get_default(Category.AR)
    assert isinstance(ar, Ar)


def test_get_default_error_invalid_category(
        subproc_record: ExtendedRecorder
) -> None:
    """
    Tests error handling in get_default, the category must be a Category,
    not e.g. a string.
    """
    tr = ToolRepository()
    with raises(RuntimeError) as err:
        tr.get_default("unknown-category-type")  # type: ignore[arg-type]
    assert "Invalid category type 'str'." in str(err.value)


def test_get_default_error_missing_mpi(subproc_record: ExtendedRecorder)\
        -> None:
    """
    Tests error handling in get_default when the optional MPI
    parameter is missing (which is required for a compiler).
    """
    tr = ToolRepository()
    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, openmp=True)
    assert str(err.value) == ("Invalid or missing mpi specification "
                              "for 'FORTRAN_COMPILER'.")

    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, mpi=True)
    assert str(err.value) == ("Invalid or missing openmp specification "
                              "for 'FORTRAN_COMPILER'.")


def test_get_default_error_missing_openmp(
        subproc_record: ExtendedRecorder
) -> None:
    """
    Tests error handling in get_default when the optional openmp
    parameter is missing (which is required for a compiler).
    """
    tr = ToolRepository()

    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, mpi=True)
    assert ("Invalid or missing openmp specification for 'FORTRAN_COMPILER'"
            in str(err.value))
    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, mpi=True, openmp='123')  # type: ignore[arg-type]
    assert str(err.value) == ("Invalid or missing openmp specification "
                              "for 'FORTRAN_COMPILER'.")


@mark.parametrize("mpi, openmp, message",
                  [(False, False, "any 'FORTRAN_COMPILER'."),
                   (False, True,
                    "'FORTRAN_COMPILER' that supports OpenMP."),
                   (True, False,
                    "'FORTRAN_COMPILER' that supports MPI."),
                   (True, True, "'FORTRAN_COMPILER' that supports MPI "
                    "and OpenMP.")])
def test_get_default_error_missing_compiler(mpi, openmp, message,
                                            subproc_record: ExtendedRecorder,
                                            monkeypatch) -> None:
    """
    Tests error handling in get_default when there is no compiler
    that fulfils the requirements with regards to OpenMP and MPI.
    """
    tr = ToolRepository()
    monkeypatch.setitem(tr, Category.FORTRAN_COMPILER, [])

    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, mpi=mpi, openmp=openmp)
    assert str(err.value) == f"Could not find {message}"


def test_get_default_error_missing_openmp_compiler(monkeypatch) -> None:
    """
    Tests error handling in get_default when there is a compiler, but it
    does not support OpenMP (which triggers additional tests in the
    ToolRepository.

    Todo: Monkeying with internal state is bad.
    """
    fc = FortranCompiler("Simply Fortran", 'sfc', 'simply', openmp_flag=None,
                         module_folder_flag="-mods", version_regex=r'([\d.]+]')

    tr = ToolRepository()
    monkeypatch.setitem(tr, Category.FORTRAN_COMPILER, [fc])

    with raises(RuntimeError) as err:
        tr.get_default(Category.FORTRAN_COMPILER, mpi=False, openmp=True)
    assert str(err.value) == "Could not find 'FORTRAN_COMPILER' that supports OpenMP."


@mark.parametrize('category', [Category.C_COMPILER,
                               Category.FORTRAN_COMPILER,
                               Category.LINKER])
def test_default_gcc_suite(category, fake_process: FakeProcess) -> None:
    """
    Tests setting default suite to "GCC" produces correct tools.
    """
    fake_process.register(['gcc', '--version'], stdout='gcc (foo) 1.2.3')
    fake_process.register(['gfortran', '--version'],
                          stdout='GNU Fortran (foo) 1.2.3')

    tr = ToolRepository()
    tr.set_default_compiler_suite('gnu')
    def_tool = tr.get_default(category, mpi=False, openmp=False)
    assert def_tool.suite == 'gnu'


@mark.parametrize('category', [Category.C_COMPILER,
                               Category.FORTRAN_COMPILER,
                               Category.LINKER])
def test_default_intel_suite(category, fake_process: FakeProcess) -> None:
    """
    Tests setting default suite to "classic-intel" produces correct tools.
    """
    fake_process.register(['icc', '-V'], stdout='icc (ICC) 1.2.3 foo')
    fake_process.register(['ifort', '-V'], stdout='ifort (IFORT) 1.2.3 foo')

    tr = ToolRepository()
    tr.set_default_compiler_suite('intel-classic')
    def_tool = tr.get_default(category, mpi=False, openmp=False)
    assert def_tool.suite == 'intel-classic'


def test_default_suite_unknown(subproc_record: ExtendedRecorder) -> None:
    repo = ToolRepository()
    with raises(RuntimeError) as err:
        repo.set_default_compiler_suite("does-not-exist")
    assert str(err.value) == ("Cannot find 'FORTRAN_COMPILER' in "
                              "the suite 'does-not-exist'.")


def test_no_tool_available(fake_process: FakeProcess) -> None:
    """
    Tests error handling if no tool is available.
    """
    # All attempted subprocesses fail.
    #
    fake_process.register([FakeProcess.any()], returncode=1)

    tr = ToolRepository()
    tr.set_default_compiler_suite("gnu")

    with raises(RuntimeError) as err:
        tr.get_default(Category.SHELL)
    assert str(err.value) == "Can't find available 'SHELL' tool. Tools are " \
                             "'sh'."

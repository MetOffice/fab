##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests ToolBox class.
"""
from pathlib import Path
from pytest import mark, raises
from pytest_subprocess.fake_process import FakeProcess

from fab.tools.ar import Ar
from fab.tools.category import Category
from fab.tools.compiler import FortranCompiler, Gcc, Gfortran, Ifort
from fab.tools.compiler_wrapper import Mpif90
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


def test_tool_repository_get_tool_with_exec_name(stub_fortran_compiler):
    '''Tests get_tool when the name of the executable is specified, e.g.
    mpif90 (instead of the Fab name mpif90-gfortran etc).

    '''
    tr = ToolRepository()
    # Keep a copy of gfortran for later
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")

    # First add just one unavailable Fortran compiler and an mpif90 wrapper:
    tr[Category.FORTRAN_COMPILER] = []
    tr.add_tool(stub_fortran_compiler)
    mpif90 = Mpif90(stub_fortran_compiler)
    tr.add_tool(mpif90)

    # If mpif90 is not available, an error is raised:
    mpif90._is_available = False
    try:
        tr.get_tool(Category.FORTRAN_COMPILER, "mpif90")
    except KeyError as err:
        assert "Unknown tool 'mpif90' in category" in str(err)

    # When using the exec name, the compiler must be available:
    mpif90._is_available = True
    f90 = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90")
    assert f90 is mpif90

    # Now add mpif90-gfortran, set mpif90-gfortran as available,
    # and mpif90-stub-fortran as unavailable. We need to make sure
    # we then get mpif90-gfortran:
    mpif90_gfortran = Mpif90(gfortran)
    tr.add_tool(mpif90_gfortran)
    mpif90._is_available = False
    mpif90_gfortran._is_available = True
    f90 = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90")
    assert f90 is mpif90_gfortran

    # Then verify using the full path
    f90 = tr.get_tool(Category.FORTRAN_COMPILER, "/some/where/mpif90")
    assert f90 is mpif90_gfortran
    assert f90.exec_path == Path("/some/where/mpif90")
    # Reset the repository, since this test messed up the compilers.
    ToolRepository._singleton = None


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


def test_get_default_error_invalid_category() -> None:
    """
    Tests error handling in get_default, the category must be a Category,
    not e.g. a string.
    """
    tr = ToolRepository()
    with raises(RuntimeError) as err:
        tr.get_default("unknown-category-type")  # type: ignore[arg-type]
    assert "Invalid category type 'str'." in str(err.value)


def test_get_default_error_missing_mpi() -> None:
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


def test_get_default_error_missing_openmp() -> None:
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
        tr.get_default(Category.FORTRAN_COMPILER, mpi=True,
                       openmp='123')  # type: ignore[arg-type]
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
    assert (str(err.value) == "Could not find 'FORTRAN_COMPILER' that "
                              "supports OpenMP.")


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
    fake_process.register(['icc', '--version'], stdout='icc (ICC) 1.2.3 foo')
    fake_process.register(['ifort', '--version'],
                          stdout='ifort (IFORT) 1.2.3 foo')

    tr = ToolRepository()
    tr.set_default_compiler_suite('intel-classic')
    def_tool = tr.get_default(category, mpi=False, openmp=False)
    assert def_tool.suite == 'intel-classic'


def test_default_suite_unknown() -> None:
    """
    Tests handling if a compiler suite is selected that does not exist.
    """
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
    assert (str(err.value) == "Can't find available 'SHELL' tool. Tools are "
                              "'sh'.")


def test_tool_repository_full_path(fake_process: FakeProcess) -> None:
    '''Tests that a user can request a tool with a full path,
    in which case the right tool should be returned with an updated
    exec name that uses the path.
    '''
    tr = ToolRepository()
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "/usr/bin/gfortran")
    assert isinstance(gfortran, Gfortran)
    assert gfortran.name == "gfortran"
    assert gfortran.exec_name == "gfortran"
    assert gfortran.exec_path == Path("/usr/bin/gfortran")

    fake_process.register(['/usr/bin/gfortran', 'a'])
    gfortran.run("a")

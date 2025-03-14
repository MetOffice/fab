##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler wrapper implementation.
'''

from pathlib import Path
from unittest import mock

import pytest

from fab.tools import (Category, CompilerWrapper, CrayCcWrapper,
                       CrayFtnWrapper, Gcc, Gfortran, Icc, Ifort,
                       Mpicc, Mpif90, ToolRepository)


def test_compiler_wrapper_compiler_getter():
    '''Tests that the compiler wrapper getter returns the
    wrapper compiler instance.
    '''
    gcc = Gcc()
    mpicc = Mpicc(gcc)
    assert mpicc.compiler is gcc


def test_compiler_wrapper_version_and_caching():
    '''Tests that the compiler wrapper reports the right version number
    from the actual compiler.
    '''
    mpicc = Mpicc(Gcc())

    # The wrapper should report the version of the wrapped compiler:
    with (mock.patch('fab.tools.compiler.Compiler.get_version',
                     return_value=(123,))):
        assert mpicc.get_version() == (123,)

    # Test that the value is cached:
    assert mpicc.get_version() == (123,)


def test_compiler_wrapper_version_consistency():
    '''Tests that the compiler wrapper and compiler must report the
    same version number:
    '''

    # The wrapper must verify that the wrapper compiler and wrapper
    # report the same version number, otherwise raise an exception.
    # The first patch changes the return value which the compiler wrapper
    # will report (since it calls Compiler.get_version), the second
    # changes the return value of the wrapper compiler instance only:

    mpicc = Mpicc(Gcc())
    with mock.patch('fab.tools.compiler.Compiler.run_version_command',
                    return_value="gcc (GCC) 8.6.0 20210514 (Red Hat "
                                 "8.5.0-20)"):
        with mock.patch.object(mpicc.compiler, 'run_version_command',
                               return_value="gcc (GCC) 8.5.0 20210514 (Red "
                                            "Hat 8.5.0-20)"):
            with pytest.raises(RuntimeError) as err:
                mpicc.get_version()
            assert ("Different version for compiler 'Gcc - gcc: gcc' (8.5.0) "
                    "and compiler wrapper 'Mpicc - mpicc-gcc: mpicc' (8.6.0)"
                    in str(err.value))


def test_compiler_wrapper_version_compiler_unavailable():
    '''Checks the behaviour if the wrapped compiler is not available.
    The wrapper should then report an empty result.
    '''

    mpicc = Mpicc(Gcc())
    with mock.patch.object(mpicc.compiler, '_is_available', False):
        with pytest.raises(RuntimeError) as err:
            assert mpicc.get_version() == ""
        assert "Cannot get version of wrapped compiler" in str(err.value)


def test_compiler_is_available_ok():
    '''Check if check_available works as expected.
    '''
    mpicc = Mpicc(Gcc())

    # Just make sure we get the right object:
    assert isinstance(mpicc, CompilerWrapper)
    assert mpicc._is_available is None

    # Make sure that the compiler-wrapper itself reports that it is available:
    # even if mpicc is not installed:
    with mock.patch('fab.tools.compiler_wrapper.CompilerWrapper.'
                    'check_available', return_value=True) as check_available:
        assert mpicc.is_available
        assert mpicc.is_available
        # Due to caching there should only be one call to check_avail
        check_available.assert_called_once_with()

    # Test that the value is indeed cached:
    assert mpicc._is_available


def test_compiler_is_available_no_version():
    '''Make sure a compiler that does not return a valid version
    is marked as not available.
    '''
    mpicc = Mpicc(Gcc())
    # Now test if get_version raises an error
    with mock.patch.object(mpicc.compiler, "get_version",
                           side_effect=RuntimeError("")):
        assert not mpicc.is_available


def test_compiler_hash():
    '''Test the hash functionality.'''
    mpicc = ToolRepository().get_tool(Category.C_COMPILER,
                                      "mpicc-gcc")
    with mock.patch.object(mpicc, "_version", (567,)):
        hash1 = mpicc.get_hash()
        assert hash1 == 4702012005

    # A change in the version number must change the hash:
    with mock.patch.object(mpicc, "_version", (89,)):
        hash2 = mpicc.get_hash()
        assert hash2 != hash1

    # A change in the name with the original version number
    # 567) must change the hash again:
    with mock.patch.object(mpicc, "_name", "new_name"):
        with mock.patch.object(mpicc, "_version", (567,)):
            hash3 = mpicc.get_hash()
            assert hash3 not in (hash1, hash2)

    # A change in the name with the modified version number
    # must change the hash again:
    with mock.patch.object(mpicc, "_name", "new_name"):
        with mock.patch.object(mpicc, "_version", (89,)):
            hash4 = mpicc.get_hash()
            assert hash4 not in (hash1, hash2, hash3)


def test_compiler_wrapper_syntax_only():
    '''Tests handling of syntax only flags in wrapper. In case of testing
    syntax only for a C compiler an exception must be raised.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    assert mpif90.has_syntax_only

    mpicc = ToolRepository().get_tool(Category.C_COMPILER, "mpicc-gcc")
    with pytest.raises(RuntimeError) as err:
        _ = mpicc.has_syntax_only
    assert "'gcc' has no has_syntax_only" in str(err.value)


def test_compiler_wrapper_module_output():
    '''Tests handling of module output_flags in a wrapper. In case of testing
    this with a C compiler, an exception must be raised.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    mpif90.set_module_output_path("/somewhere")
    assert mpif90.compiler._module_output_path == "/somewhere"

    mpicc = ToolRepository().get_tool(Category.C_COMPILER, "mpicc-gcc")
    with pytest.raises(RuntimeError) as err:
        mpicc.set_module_output_path("/tmp")
    assert "'gcc' has no 'set_module_output_path' function" in str(err.value)


def test_compiler_wrapper_fortran_with_add_args():
    '''Tests that additional arguments are handled as expected in
    a wrapper.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    mpif90.set_module_output_path("/module_out")
    with mock.patch.object(mpif90.compiler, "run", mock.MagicMock()):
        with pytest.warns(UserWarning, match="Removing managed flag"):
            mpif90.compile_file(Path("a.f90"), "a.o",
                                add_flags=["-J/b", "-O3"], openmp=False,
                                syntax_only=True)
        # Notice that "-J/b" has been removed
        mpif90.compiler.run.assert_called_with(
            cwd=Path('.'), additional_parameters=['-c', "-O3",
                                                  '-fsyntax-only',
                                                  '-J', '/module_out',
                                                  'a.f90', '-o', 'a.o'])


def test_compiler_wrapper_fortran_with_add_args_unnecessary_openmp():
    '''Tests that additional arguments are handled as expected in
    a wrapper if also the openmp flags are specified.'''
    mpif90 = ToolRepository().get_tool(Category.FORTRAN_COMPILER,
                                       "mpif90-gfortran")
    mpif90.set_module_output_path("/module_out")
    with mock.patch.object(mpif90.compiler, "run", mock.MagicMock()):
        with pytest.warns(UserWarning,
                          match="explicitly provided. OpenMP should be "
                                "enabled in the BuildConfiguration"):
            mpif90.compile_file(Path("a.f90"), "a.o",
                                add_flags=["-fopenmp", "-O3"],
                                openmp=True, syntax_only=True)
            mpif90.compiler.run.assert_called_with(
                cwd=Path('.'),
                additional_parameters=['-c', '-fopenmp', '-fopenmp', '-O3',
                                       '-fsyntax-only', '-J', '/module_out',
                                       'a.f90', '-o', 'a.o'])


def test_compiler_wrapper_c_with_add_args():
    '''Tests that additional arguments are handled as expected in a
    compiler wrapper. Also verify that requesting Fortran-specific options
    like syntax-only with the C compiler raises a runtime error.
    '''

    mpicc = ToolRepository().get_tool(Category.C_COMPILER,
                                      "mpicc-gcc")
    with mock.patch.object(mpicc.compiler, "run", mock.MagicMock()):
        # Normal invoke of the C compiler, make sure add_flags are
        # passed through:
        mpicc.compile_file(Path("a.f90"), "a.o", openmp=False,
                           add_flags=["-O3"])
        mpicc.compiler.run.assert_called_with(
            cwd=Path('.'), additional_parameters=['-c', "-O3", 'a.f90',
                                                  '-o', 'a.o'])
        # Invoke C compiler with syntax-only flag (which is only supported
        # by Fortran compilers), which should raise an exception.
        with pytest.raises(RuntimeError) as err:
            mpicc.compile_file(Path("a.f90"), "a.o", openmp=False,
                               add_flags=["-O3"], syntax_only=True)
    assert ("Syntax-only cannot be used with compiler 'mpicc-gcc'."
            in str(err.value))

    # Check that providing the openmp flag in add_flag raises a warning:
    with mock.patch.object(mpicc.compiler, "run", mock.MagicMock()):
        with pytest.warns(UserWarning,
                          match="explicitly provided. OpenMP should be "
                                "enabled in the BuildConfiguration"):
            mpicc.compile_file(Path("a.f90"), "a.o",
                               add_flags=["-fopenmp", "-O3"],
                               openmp=True)
            mpicc.compiler.run.assert_called_with(
                cwd=Path('.'),
                additional_parameters=['-c', '-fopenmp', '-fopenmp', '-O3',
                                       'a.f90', '-o', 'a.o'])


def test_compiler_wrapper_flags_independent():
    '''Tests that flags set in the base compiler will be accessed in the
    wrapper, but not the other way round.'''
    gcc = Gcc()
    mpicc = Mpicc(gcc)
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert gcc.flags == []
    assert mpicc.flags == []
    # Setting flags in gcc must become visible in the wrapper compiler:
    gcc.add_flags(["-a", "-b"])
    assert gcc.flags == ["-a", "-b"]
    assert mpicc.flags == ["-a", "-b"]
    assert mpicc.openmp_flag == gcc.openmp_flag

    # Test  a compiler wrapper correctly queries the wrapper compiler for
    # openmp flag: Set the wrapper to have no _openmp_flag (which is
    # actually the default, since the wrapper never sets its own flag), but
    # gcc does have a flag, so mpicc should report that is supports openmp.
    # mpicc.openmp calls openmp of its base class (Compiler), which queries
    # if an openmp flag is defined. This query must go to the openmp property,
    # since the wrapper overwrites this property to return the wrapped
    # compiler's flag (and not the wrapper's flag, which would not be defined)
    with mock.patch.object(mpicc, "_openmp_flag", ""):
        assert mpicc._openmp_flag == ""
        assert mpicc.openmp

    # Adding flags to the wrapper should not affect the wrapped compiler:
    mpicc.add_flags(["-d", "-e"])
    assert gcc.flags == ["-a", "-b"]
    # And the compiler wrapper should reports the wrapped compiler's flag
    # followed by the wrapper flag (i.e. the wrapper flag can therefore
    # overwrite the wrapped compiler's flags)
    assert mpicc.flags == ["-a", "-b", "-d", "-e"]


def test_compiler_wrapper_flags_with_add_arg():
    '''Tests that flags set in the base compiler will be accessed in the
    wrapper if also additional flags are specified.'''
    gcc = Gcc()
    mpicc = Mpicc(gcc)
    gcc.add_flags(["-a", "-b"])
    mpicc.add_flags(["-d", "-e"])

    # Check that the flags are assembled in the right order in the
    # actual compiler call: first the wrapper compiler flag, then
    # the wrapper flag, then additional flags
    with mock.patch.object(mpicc.compiler, "run", mock.MagicMock()):
        mpicc.compile_file(Path("a.f90"), "a.o", add_flags=["-f"],
                           openmp=True)
        mpicc.compiler.run.assert_called_with(
                cwd=Path('.'),
                additional_parameters=["-c", "-fopenmp", "-a", "-b", "-d",
                                       "-e", "-f", "a.f90", "-o", "a.o"])


def test_compiler_wrapper_flags_without_add_arg():
    '''Tests that flags set in the base compiler will be accessed in the
    wrapper if no additional flags are specified.'''
    gcc = Gcc()
    mpicc = Mpicc(gcc)
    gcc.add_flags(["-a", "-b"])
    mpicc.add_flags(["-d", "-e"])
    # Check that the flags are assembled in the right order in the
    # actual compiler call: first the wrapper compiler flag, then
    # the wrapper flag, then additional flags
    with mock.patch.object(mpicc.compiler, "run", mock.MagicMock()):
        # Test if no add_flags are specified:
        mpicc.compile_file(Path("a.f90"), "a.o", openmp=True)
        mpicc.compiler.run.assert_called_with(
                cwd=Path('.'),
                additional_parameters=["-c", "-fopenmp", "-a", "-b", "-d",
                                       "-e", "a.f90", "-o", "a.o"])


def test_compiler_wrapper_mpi_gcc():
    '''Tests the MPI enables gcc class.'''
    mpi_gcc = Mpicc(Gcc())
    assert mpi_gcc.name == "mpicc-gcc"
    assert str(mpi_gcc) == "Mpicc - mpicc-gcc: mpicc"
    assert isinstance(mpi_gcc, CompilerWrapper)
    assert mpi_gcc.category == Category.C_COMPILER
    assert mpi_gcc.mpi
    assert mpi_gcc.suite == "gnu"


def test_compiler_wrapper_mpi_gfortran():
    '''Tests the MPI enabled gfortran class.'''
    mpi_gfortran = Mpif90(Gfortran())
    assert mpi_gfortran.name == "mpif90-gfortran"
    assert str(mpi_gfortran) == "Mpif90 - mpif90-gfortran: mpif90"
    assert isinstance(mpi_gfortran, CompilerWrapper)
    assert mpi_gfortran.category == Category.FORTRAN_COMPILER
    assert mpi_gfortran.mpi
    assert mpi_gfortran.suite == "gnu"


def test_compiler_wrapper_mpi_icc():
    '''Tests the MPI enabled icc class.'''
    mpi_icc = Mpicc(Icc())
    assert mpi_icc.name == "mpicc-icc"
    assert str(mpi_icc) == "Mpicc - mpicc-icc: mpicc"
    assert isinstance(mpi_icc, CompilerWrapper)
    assert mpi_icc.category == Category.C_COMPILER
    assert mpi_icc.mpi
    assert mpi_icc.suite == "intel-classic"


def test_compiler_wrapper_mpi_ifort():
    '''Tests the MPI enabled ifort class.'''
    mpi_ifort = Mpif90(Ifort())
    assert mpi_ifort.name == "mpif90-ifort"
    assert str(mpi_ifort) == "Mpif90 - mpif90-ifort: mpif90"
    assert isinstance(mpi_ifort, CompilerWrapper)
    assert mpi_ifort.category == Category.FORTRAN_COMPILER
    assert mpi_ifort.mpi
    assert mpi_ifort.suite == "intel-classic"


def test_compiler_wrapper_cray_icc():
    '''Tests the Cray wrapper for icc.'''
    craycc = CrayCcWrapper(Icc())
    assert craycc.name == "craycc-icc"
    assert str(craycc) == "CrayCcWrapper - craycc-icc: cc"
    assert isinstance(craycc, CompilerWrapper)
    assert craycc.category == Category.C_COMPILER
    assert craycc.mpi
    assert craycc.suite == "intel-classic"


def test_compiler_wrapper_cray_ifort():
    '''Tests the Cray wrapper for ifort.'''
    crayftn = CrayFtnWrapper(Ifort())
    assert crayftn.name == "crayftn-ifort"
    assert str(crayftn) == "CrayFtnWrapper - crayftn-ifort: ftn"
    assert isinstance(crayftn, CompilerWrapper)
    assert crayftn.category == Category.FORTRAN_COMPILER
    assert crayftn.mpi
    assert crayftn.suite == "intel-classic"


def test_compiler_wrapper_cray_gcc():
    '''Tests the Cray wrapper for gcc.'''
    craycc = CrayCcWrapper(Gcc())
    assert craycc.name == "craycc-gcc"

    assert str(craycc) == "CrayCcWrapper - craycc-gcc: cc"
    assert isinstance(craycc, CompilerWrapper)
    assert craycc.category == Category.C_COMPILER
    assert craycc.mpi
    assert craycc.suite == "gnu"


def test_compiler_wrapper_cray_gfortran():
    '''Tests the Cray wrapper for gfortran.'''
    crayftn = CrayFtnWrapper(Gfortran())
    assert crayftn.name == "crayftn-gfortran"
    assert str(crayftn) == "CrayFtnWrapper - crayftn-gfortran: ftn"
    assert isinstance(crayftn, CompilerWrapper)
    assert crayftn.category == Category.FORTRAN_COMPILER
    assert crayftn.mpi
    assert crayftn.suite == "gnu"

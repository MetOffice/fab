##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the compiler wrapper implementation.
"""
from pathlib import Path

from pytest import raises, warns
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import ExtendedRecorder, call_list, not_found_callback

from fab.build_config import BuildConfig
from fab.tools.category import Category
from fab.tools.compiler import CCompiler, FortranCompiler
from fab.tools.compiler_wrapper import (CompilerWrapper,
                                        CrayCcWrapper, CrayFtnWrapper,
                                        Mpicc, Mpif90)


def test_compiler_getter(stub_c_compiler: CCompiler,
                         subproc_record: ExtendedRecorder) -> None:
    """
    Tests that the compiler wrapper getter returns the
    wrapper compiler instance.
    """
    mpicc = Mpicc(stub_c_compiler)
    assert mpicc.compiler is stub_c_compiler


def test_version_and_caching(stub_c_compiler: CCompiler,
                             fake_process: FakeProcess) -> None:
    """
    Tests that the compiler wrapper reports the right version number
    from the actual compiler.
    """
    fake_process.register(['scc', '--version'], stdout='1.2.3')
    fake_process.register(['mpicc', '--version'], stdout='1.2.3')
    mpicc = Mpicc(stub_c_compiler)

    # The wrapper should report the version of the wrapped compiler:
    assert mpicc.get_version() == (1, 2, 3)

    # Test that the value is cached:
    assert mpicc.get_version() == (1, 2, 3)
    assert call_list(fake_process) == [
        ['scc', '--version'],
        ['mpicc', '--version']
    ]


def test_version_consistency(stub_c_compiler: CCompiler,
                             fake_process: FakeProcess) -> None:
    """
    Tests that the compiler wrapper and compiler must report the
    same version number:
    """
    # The wrapper must verify that the wrapper compiler and wrapper
    # report the same version number, otherwise raise an exception.
    # The first patch changes the return value which the compiler wrapper
    # will report (since it calls Compiler.get_version), the second
    # changes the return value of the wrapper compiler instance only:
    fake_process.register(['scc', '--version'], stdout='1.2.3')
    fake_process.register(['mpicc', '--version'], stdout='4.5.6')

    mpicc = Mpicc(stub_c_compiler)
    with raises(RuntimeError) as err:
        mpicc.get_version()
    assert str(err.value) == ("Different version for compiler "
                              "'CCompiler - some C compiler: scc' (1.2.3) and "
                              "compiler wrapper 'Mpicc - mpicc-some C "
                              "compiler: mpicc' (4.5.6).")


def test_version_compiler_unavailable(stub_c_compiler: CCompiler,
                                      fake_process: FakeProcess) -> None:
    """
    Tests availability check when wrapped compiler is missing.
    """
    fake_process.register(['scc', '--version'], callback=not_found_callback)
    fake_process.register(['mpicc', '--version'], stdout='1.2.3')
    mpicc = Mpicc(stub_c_compiler)
    with raises(RuntimeError) as err:
        assert mpicc.get_version() == ""
    assert str(err.value) == ("Cannot get version of wrapped compiler "
                              "'CCompiler - some C compiler: scc")


def test_compiler_is_available_ok(stub_c_compiler: CCompiler,
                                  fake_process: FakeProcess) -> None:
    """
    Tests availability check when everything is okay.
    """
    fake_process.register(['scc', '--version'], stdout='1.2.3')
    fake_process.register(['mpicc', '--version'], stdout='1.2.3')
    mpicc = Mpicc(stub_c_compiler)

    # Just make sure we get the right object:
    assert isinstance(mpicc, CompilerWrapper)
    assert mpicc.is_available is True


def test_compiler_is_available_no_version(stub_c_compiler: CCompiler,
                                          fake_process: FakeProcess) -> None:
    """
    Make sure a compiler that does not return a valid version
    is marked as not available.
    """
    fake_process.register(['scc', '--version'], callback=not_found_callback)
    mpicc = Mpicc(stub_c_compiler)
    # Now test if get_version raises an error
    assert not mpicc.is_available

    fake_process.register(['scc', '--version'], stdout='1.2.3')
    fake_process.register(['mpicc', '--version'], callback=not_found_callback)
    assert not mpicc.is_available


def test_compiler_hash(fake_process: FakeProcess) -> None:
    """
    Test the hash functionality.
    """
    fake_process.register(['tcc', '--version'], stdout='5.6.7')
    fake_process.register(['mpicc', '--version'], stdout='5.6.7')
    cc1 = CCompiler('test C compiler', 'tcc', 'test',
                    version_regex=r'([\d.]+)')
    mpicc1 = Mpicc(cc1)
    hash1 = mpicc1.get_hash()
    assert hash1 == 5953380633

    # A change in the version number must change the hash:
    fake_process.register(['tcc', '--version'], stdout='8.9')
    fake_process.register(['mpicc', '--version'], stdout='8.9')
    cc2 = CCompiler('test C compiler', 'tcc', 'test',
                    version_regex=r'([\d.]+)')
    mpicc2 = Mpicc(cc2)
    hash2 = mpicc2.get_hash()
    assert hash2 != hash1

    # A change in the name with the original version number
    # 567) must change the hash again:
    fake_process.register(['tcc', '--version'], stdout='5.6.7')
    fake_process.register(['mpicc', '--version'], stdout='5.6.7')
    cc3 = CCompiler('New test C compiler', 'tcc', 'test',
                    version_regex=r'([\d.]+)')
    mpicc3 = Mpicc(cc3)
    hash3 = mpicc3.get_hash()
    assert hash3 not in (hash1, hash2)

    # A change in the name with the modified version number
    # must change the hash again:
    fake_process.register(['tcc', '--version'], stdout='8.9')
    fake_process.register(['mpicc', '--version'], stdout='8.9')
    cc4 = CCompiler('New test C compiler', 'tcc', 'test',
                    version_regex=r'([\d.]+)')
    mpicc4 = Mpicc(cc4)
    hash4 = mpicc4.get_hash()
    assert hash4 not in (hash1, hash2, hash3)


def test_syntax_only(stub_c_compiler: CCompiler,
                     subproc_record: ExtendedRecorder) -> None:
    """
    Tests handling of syntax only flags in wrapper. In case of testing
    syntax only for a C compiler an exception must be raised.
    """
    fc = FortranCompiler('test Fortran', 'tfc', 'test', r'[\d.]+',
                         syntax_only_flag='-syntax')
    mpif90 = Mpif90(fc)

    assert mpif90.has_syntax_only

    mpicc = Mpicc(stub_c_compiler)
    with raises(RuntimeError) as err:
        _ = mpicc.has_syntax_only
    assert str(err.value) == "Compiler 'some C compiler' has no has_syntax_only."


def test_module_output(stub_fortran_compiler: FortranCompiler,
                       stub_c_compiler: CCompiler):
    """
    Tests handling of module output_flags in a wrapper. In case of testing
    this with a C compiler, an exception must be raised.

    Todo: Monkeying with internal state.
    """
    stub_fortran_compiler.set_module_output_path(Path('/somewhere'))
    assert stub_fortran_compiler._module_output_path == "/somewhere"
    mpif90 = Mpif90(stub_fortran_compiler)
    mpif90.set_module_output_path(Path("/somewhere"))
    assert stub_fortran_compiler._module_output_path == "/somewhere"

    mpicc = Mpicc(stub_c_compiler)
    with raises(RuntimeError) as err:
        mpicc.set_module_output_path(Path("/tmp"))
    assert str(err.value) == ("Compiler 'some C compiler' has "
                              "no 'set_module_output_path' function.")


def test_fortran_with_add_args(stub_fortran_compiler: FortranCompiler,
                               stub_configuration: BuildConfig,
                               subproc_record: ExtendedRecorder) -> None:
    """
    Tests that additional arguments are handled as expected in
    a wrapper.
    """
    mpif90 = Mpif90(stub_fortran_compiler)
    mpif90.set_module_output_path(Path('/module_out'))

    with warns(UserWarning, match="Removing managed flag"):
        mpif90.compile_file(Path("a.f90"), Path('a.o'),
                            add_flags=["-mods", "/b", "-O3"],
                            config=stub_configuration)
    # Notice that "-mods /b" has been removed
    assert subproc_record.invocations() == [
        ['mpif90', '-c', "-O3", '-mods', '/module_out', 'a.f90', '-o', 'a.o']
    ]
    assert subproc_record.extras()[0]['cwd'] == '.'


def test_fortran_unnecessary_openmp(stub_fortran_compiler: FortranCompiler,
                                    stub_configuration: BuildConfig,
                                    subproc_record: ExtendedRecorder) -> None:
    """
    Tests that additional arguments are handled as expected in
    a wrapper if also the openmp flags are specified.
    """
    mpif90 = Mpif90(stub_fortran_compiler)
    mpif90.set_module_output_path(Path('/module_out'))

    with warns(UserWarning,
               match="explicitly provided. OpenMP should be "
                     "enabled in the BuildConfiguration"):
        mpif90.compile_file(Path("a.f90"), Path('a.o'),
                            add_flags=["-omp", "-O3"],
                            config=stub_configuration)
    assert subproc_record.invocations() == [
        ['mpif90', '-c', '-omp', '-O3', '-mods', '/module_out',
         'a.f90', '-o', 'a.o']
    ]
    assert subproc_record.extras()[0]['cwd'] == '.'


def test_c_with_add_args(stub_c_compiler: CCompiler,
                         stub_configuration: BuildConfig,
                         subproc_record: ExtendedRecorder) -> None:
    """
    Tests that additional arguments are handled as expected in a
    compiler wrapper. Also verify that requesting Fortran-specific options
    like syntax-only with the C compiler raises a runtime error.
    """
    mpicc = Mpicc(stub_c_compiler)

    # Normal invoke of the C compiler, make sure add_flags are
    # passed through:
    mpicc.compile_file(Path("a.f90"), Path('a.o'),
                       add_flags=["-O3"],
                       config=stub_configuration)

    # Invoke C compiler with syntax-only flag (which is only supported
    # by Fortran compilers), which should raise an exception.
    with raises(RuntimeError) as err:
        mpicc.compile_file(Path("a.f90"), Path('a.o'),
                           add_flags=["-O3"], syntax_only=True,
                           config=stub_configuration)
    assert str(err.value) == "Syntax-only cannot be used with compiler 'mpicc-some C compiler'."

    # Check that providing the openmp flag in add_flag raises a warning:
    with warns(UserWarning,
               match="explicitly provided. OpenMP should be "
                     "enabled in the BuildConfiguration"):
        mpicc.compile_file(Path("a.f90"), Path('a.o'),
                           add_flags=["-omp", "-O3"],
                           config=stub_configuration)

        assert subproc_record.invocations() == [
            ['mpicc', '-c', "-O3", 'a.f90', '-o', 'a.o'],
            ['mpicc', '-c', '-omp', '-O3', 'a.f90', '-o', 'a.o']
        ]
        assert subproc_record.extras()[0]['cwd'] == '.'
        assert subproc_record.extras()[1]['cwd'] == '.'


def test_flags_independent(stub_c_compiler: CCompiler,
                           stub_configuration: BuildConfig,
                           subproc_record: ExtendedRecorder) -> None:
    """
    Tests that flags set in the base compiler will be accessed in the
    wrapper, but not the other way round.
    """
    wrapper = Mpicc(stub_c_compiler)

    assert stub_c_compiler.get_flags() == []
    assert wrapper.get_flags() == []

    stub_c_compiler.add_flags(["-a", "-b"])
    assert stub_c_compiler.get_flags() == ["-a", "-b"]
    assert wrapper.get_flags() == ['-a', '-b']
    assert wrapper.openmp_flag == stub_c_compiler.openmp_flag

    # Adding flags to the wrapper should not affect the wrapped compiler:
    wrapper.add_flags(["-d", "-e"])
    assert stub_c_compiler.get_flags() == ['-a', '-b']
    # And the compiler wrapper should report both sets of flags.
    assert wrapper.get_flags() == ['-a', '-b', "-d", "-e"]

    wrapper.compile_file(Path("a.f90"), Path('a.o'), add_flags=['-f'],
                         config=stub_configuration)
    assert subproc_record.invocations() == [
        ['mpicc', "-a", "-b", "-c", "-d", "-e", "-f", "a.f90", "-o", 'a.o']
    ]
    assert subproc_record.extras()[0]['cwd'] == '.'


def test_args_without_add_arg(stub_c_compiler: CCompiler,
                              stub_configuration: BuildConfig,
                              subproc_record: ExtendedRecorder) -> None:
    """
    Tests that flags set in the base compiler will be accessed in the
    wrapper if no additional flags are specified.
    """
    wrapper = CompilerWrapper('wrapper', 'wrp', compiler=stub_c_compiler)

    stub_c_compiler.add_flags(["-a", "-b"])
    wrapper.add_flags(["-d", "-e"])

    wrapper.compile_file(Path("a.f90"), Path('a.o'), config=stub_configuration)
    assert subproc_record.invocations() == [
        ['wrp', "-a", "-b", "-c", "-d", "-e", "a.f90", "-o", 'a.o']
    ]
    assert subproc_record.extras()[0]['cwd'] == '.'


def test_mpi_c(stub_c_compiler: CCompiler) -> None:
    """
    Tests the MPI enabled icc class.
    """
    mpi_icc = Mpicc(stub_c_compiler)
    assert mpi_icc.name == "mpicc-some C compiler"
    assert str(mpi_icc) == "Mpicc - mpicc-some C compiler: mpicc"
    assert isinstance(mpi_icc, CompilerWrapper)
    assert mpi_icc.category == Category.C_COMPILER
    assert mpi_icc.mpi
    assert mpi_icc.suite == "stub"


def test_mpi_fortran(stub_fortran_compiler: FortranCompiler) -> None:
    """
    Tests the MPI enabled ifort class.
    """
    mpi_ifort = Mpif90(stub_fortran_compiler)
    assert mpi_ifort.name == "mpif90-some Fortran compiler"
    assert str(mpi_ifort) == "Mpif90 - mpif90-some Fortran compiler: mpif90"
    assert isinstance(mpi_ifort, CompilerWrapper)
    assert mpi_ifort.category == Category.FORTRAN_COMPILER
    assert mpi_ifort.mpi
    assert mpi_ifort.suite == "stub"


def test_cray_c(stub_c_compiler: CCompiler) -> None:
    """
    Tests the Cray wrapper for gcc.
    """
    craycc = CrayCcWrapper(stub_c_compiler)
    assert craycc.name == "craycc-some C compiler"
    assert str(craycc) == "CrayCcWrapper - craycc-some C compiler: cc"
    assert isinstance(craycc, CompilerWrapper)
    assert craycc.category == Category.C_COMPILER
    assert craycc.mpi
    assert craycc.suite == "stub"


def test_cray_fortran(stub_fortran_compiler: FortranCompiler) -> None:
    """
    Tests the Cray wrapper for gfortran.
    """
    crayftn = CrayFtnWrapper(stub_fortran_compiler)
    assert crayftn.name == "crayftn-some Fortran compiler"
    assert str(crayftn) == "CrayFtnWrapper - crayftn-some Fortran compiler: ftn"
    assert isinstance(crayftn, CompilerWrapper)
    assert crayftn.category == Category.FORTRAN_COMPILER
    assert crayftn.mpi
    assert crayftn.suite == "stub"

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Exercises linker tooling.
"""
from pathlib import Path
import warnings

from pytest import mark, raises, warns
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import ExtendedRecorder, not_found_callback

from fab.build_config import BuildConfig
from fab.tools.category import Category
from fab.tools.compiler import CCompiler, FortranCompiler
from fab.tools.compiler_wrapper import CompilerWrapper, Mpif90
from fab.tools.linker import Linker


def test_c_linker(stub_c_compiler: CCompiler) -> None:
    """
    Tests construction from C compiler
    """
    linker = Linker(stub_c_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-some C compiler"
    assert linker.exec_name == "scc"
    assert linker.suite == "stub"
    assert linker.get_flags() == []
    assert linker.output_flag == "-o"


def test_fortran_linker(stub_fortran_compiler: FortranCompiler) -> None:
    linker = Linker(stub_fortran_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-some Fortran compiler"
    assert linker.exec_name == "sfc"
    assert linker.suite == "stub"
    assert linker.get_flags() == []


@mark.parametrize("mpi", [True, False])
def test_linker_mpi(mpi: bool) -> None:
    """
    Tests linker wrappers handle MPI as expected.
    """
    compiler = CCompiler("some C compiler", 'scc', 'some', r'([\d.]+)',
                         mpi=mpi)
    linker = Linker(compiler)
    assert linker.mpi == mpi

    wrapped_linker = Linker(compiler, linker=linker)
    assert wrapped_linker.mpi == mpi


@mark.parametrize("openmp", [True, False])
def test_linker_openmp(openmp: bool) -> None:
    """
    Test that linker wrappers handle openmp as expected.

    Note that a compiler detects support for OpenMP by checking if an openmp
    flag is defined.
    """
    if openmp:
        compiler = CCompiler("some C compiler", 'scc', 'some', r'([\d.]+)',
                             openmp_flag='-omp')
    else:
        compiler = CCompiler("some C compiler", 'scc', 'some', r'([\d.]+)',
                             openmp_flag='')
    linker = Linker(compiler=compiler)
    assert linker.openmp == openmp

    wrapped_linker = Linker(compiler, linker=linker)
    assert wrapped_linker.openmp == openmp


def test_check_available(stub_c_compiler: CCompiler,
                         fake_process: FakeProcess) -> None:
    """
    Tests the is_available functionality when compiler is present.
    """
    fake_process.register(['scc', '--version'], stdout='1.2.3')
    linker = Linker(stub_c_compiler)
    assert linker.check_available()

    # Then test the usage of a linker wrapper. The linker will call the
    # corresponding function in the wrapper linker:
    wrapped_linker = Linker(stub_c_compiler, linker=linker)
    assert wrapped_linker.check_available()


def test_check_unavailable(stub_c_compiler: CCompiler,
                           fake_process: FakeProcess) -> None:
    """
    Tests is_available functionality when compiler is missing.
    """
    fake_process.register(['scc', '--version'], callback=not_found_callback)
    linker = Linker(stub_c_compiler)
    assert linker.check_available() is False


# ====================
# Managing lib flags:
# ====================
def test_linker_get_lib_flags(stub_fortran_compiler: FortranCompiler) -> None:
    """
    Tests linker provides a map of library names, each leading to a list of
    linker flags
    """
    test_unit = Linker(stub_fortran_compiler)
    test_unit.add_lib_flags('netcdf', ['-lnetcdff', '-lnetcdf'])
    assert test_unit.get_lib_flags("netcdf") == ["-lnetcdff", "-lnetcdf"]


def test_get_lib_flags_unknown(stub_c_compiler: CCompiler) -> None:
    """
    Tests sinker raises an error if flags are requested for a library
    that is unknown.
    """
    linker = Linker(compiler=stub_c_compiler)
    with raises(RuntimeError) as err:
        linker.get_lib_flags("unknown")
    assert str(err.value) == "Unknown library name: 'unknown'"


def test_add_lib_flags(stub_c_compiler: CCompiler) -> None:
    """
    Tests linker provides a way to add a new set of flags for a library.
    """
    linker = Linker(compiler=stub_c_compiler)
    linker.add_lib_flags("xios", ["-L", "xios/lib", "-lxios"])

    # Make sure we can get it back. The order should be maintained.
    result = linker.get_lib_flags("xios")
    assert result == ["-L", "xios/lib", "-lxios"]


def test_add_lib_flags_overwrite_defaults(
        stub_fortran_compiler: FortranCompiler
) -> None:
    """
    Linker should provide a way to replace the default flags for
    a library.
    """
    test_unit = Linker(stub_fortran_compiler)
    test_unit.add_lib_flags('netcdf', ['-lnetcdff', '-lnetcdf'])

    result = test_unit.get_lib_flags("netcdf")
    assert result == ["-lnetcdff", "-lnetcdf"]

    # Replace them with another set of flags.
    warn_message = 'Replacing existing flags for library netcdf'
    with warns(UserWarning, match=warn_message):
        test_unit.add_lib_flags(
            "netcdf", ["-L", "netcdf/lib", "-lnetcdf"]
        )

    # Test that we can see our custom flags
    result = test_unit.get_lib_flags("netcdf")
    assert result == ["-L", "netcdf/lib", "-lnetcdf"]


def test_linker_add_lib_flags_overwrite_silent(stub_linker: Linker) -> None:
    """
    Tests replacing arguments raises no warning.
    """
    stub_linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    assert stub_linker.get_lib_flags("customlib") == ["-lcustom", "-jcustom"]

    # Replace with another set of flags.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        stub_linker.add_lib_flags("customlib", ["-t", "-b"],
                                  silent_replace=True)

    # Test that we can see our custom flags
    result = stub_linker.get_lib_flags("customlib")
    assert result == ["-t", "-b"]


class TestLinkerLinking:
    def test_c(self, stub_c_compiler: CCompiler,
               stub_configuration: BuildConfig,
               subproc_record: ExtendedRecorder) -> None:
        """
        Tests linkwhen no additional libraries are specified.
        """
        linker = Linker(compiler=stub_c_compiler)
        # Add a library to the linker, but don't use it in the link step
        linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

        linker.link([Path("a.o")], Path("a.out"), config=stub_configuration)
        assert subproc_record.invocations() == [
            ['scc', "a.o", "-o", "a.out"]
        ]


def test_c_with_libraries(stub_c_compiler: CCompiler,
                          stub_configuration: BuildConfig,
                          subproc_record: ExtendedRecorder) -> None:
    """
    Tests link command line when additional libraries are specified.
    """
    linker = Linker(compiler=stub_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

    linker.link([Path("a.o")], Path("a.out"), libs=["customlib"],
                add_flags=["-l", "something_additional"],
                config=stub_configuration)

    # The order of the 'libs' list should be maintained
    assert subproc_record.invocations() == [
        ["scc", "a.o", "-lcustom", "-jcustom", "-l", "something_additional",
         "-o", "a.out"]
    ]


def test_c_with_libraries_and_post_flags(stub_c_compiler: CCompiler,
                                         stub_configuration: BuildConfig,
                                         subproc_record: ExtendedRecorder) -> None:
    """
    Tests link command line when a library and additional flags are specified.
    """
    linker = Linker(compiler=stub_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_post_lib_flags(["-extra-flag"])

    linker.link([Path("a.o")], Path("a.out"),
                libs=["customlib"], config=stub_configuration)
    assert subproc_record.invocations() == [
        ['scc', "a.o", "-lcustom", "-jcustom", "-extra-flag", "-o", "a.out"]
    ]


def test_c_with_libraries_and_pre_flags(stub_c_compiler: CCompiler,
                                        stub_configuration: BuildConfig,
                                        subproc_record: ExtendedRecorder) -> None:
    """
    Tests link command line when a library and additional flags are specified.
    """
    linker = Linker(compiler=stub_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_pre_lib_flags(["-L", "/common/path/"])

    linker.link([Path("a.o")], Path("a.out"),
                libs=["customlib"], config=stub_configuration)
    assert subproc_record.invocations() == [
        ['scc', "a.o", "-L", "/common/path/",
         "-lcustom", "-jcustom", "-o", "a.out"]
    ]


def test_c_with_unknown_library(stub_c_compiler: CCompiler,
                                stub_configuration: BuildConfig) -> None:
    """
    Tests link tool raises an error when unknow libraries are specified.
    """
    linker = Linker(compiler=stub_c_compiler)

    with raises(RuntimeError) as err:
        # Try to use "customlib" when we haven't added it to the linker
        linker.link([Path("a.o")], Path("a.out"),
                    libs=["customlib"], config=stub_configuration)
    assert str(err.value) == "Unknown library name: 'customlib'"


def test_add_compiler_flag(stub_c_compiler: CCompiler,
                           stub_configuration: BuildConfig,
                           subproc_record: ExtendedRecorder) -> None:
    """
    Tests an argument added to the compiler will appear in the link line.

    Even if the arguments are modified after creating the linker.
    """
    linker = Linker(compiler=stub_c_compiler)
    stub_c_compiler.add_flags("-my-flag")
    linker.link([Path("a.o")], Path("a.out"), config=stub_configuration)
    assert subproc_record.invocations() == [
        ['scc', '-my-flag', 'a.o', '-o', 'a.out']
    ]


def test_linker_all_flag_types(stub_c_compiler: CCompiler,
                               stub_configuration: BuildConfig,
                               subproc_record: ExtendedRecorder) -> None:
    """
    Tests linker arguments are used in the correct order.

    Todo: Monkeying with private state.
    """

    linker = Linker(compiler=stub_c_compiler)

    stub_c_compiler.add_flags(["-compiler-flag1", "-compiler-flag2"])

    linker.add_flags(["-linker-flag1", "-linker-flag2"])
    linker.add_pre_lib_flags(["-prelibflag1", "-prelibflag2"])
    linker.add_lib_flags("customlib1", ["-lib1flag1", "lib1flag2"])
    linker.add_lib_flags("customlib2", ["-lib2flag1", "lib2flag2"])
    linker.add_post_lib_flags(["-postlibflag1", "-postlibflag2"])

    stub_configuration._openmp = True
    linker.link([Path("a.o")], Path("a.out"),
                libs=["customlib2", "customlib1"], config=stub_configuration)
    assert subproc_record.invocations() == [
        ['scc', "-linker-flag1", "-linker-flag2",
         "-compiler-flag1", "-compiler-flag2",
         "-omp",
         "a.o",
         "-prelibflag1", "-prelibflag2",
         "-lib2flag1", "lib2flag2",
         "-lib1flag1", "lib1flag2",
         "-postlibflag1", "-postlibflag2",
         "-o", "a.out"]
    ]


def test_linker_nesting(stub_c_compiler: CCompiler,
                        stub_configuration: BuildConfig,
                        subproc_record: ExtendedRecorder) -> None:
    """
    Tests linker arguments appear in correct order.

    Todo: Monkeying with private state.
    """
    linker1 = Linker(compiler=stub_c_compiler)
    linker1.add_pre_lib_flags(["pre_lib1"])
    linker1.add_lib_flags("lib_a", ["a_from_1"])
    linker1.add_lib_flags("lib_c", ["c_from_1"])
    linker1.add_post_lib_flags(["post_lib1"])

    linker2 = Linker(stub_c_compiler, linker=linker1)
    linker2.add_pre_lib_flags(["pre_lib2"])
    linker2.add_lib_flags("lib_b", ["b_from_2"])
    linker2.add_lib_flags("lib_c", ["c_from_2"])

    linker1.add_post_lib_flags(["post_lib2"])

    stub_configuration._openmp = True
    linker2.link([Path("a.o")], Path("a.out"),
                 libs=["lib_a", "lib_b", "lib_c"], config=stub_configuration)
    assert subproc_record.invocations() == [
        ["scc", "-omp", "a.o", "pre_lib2", "pre_lib1", "a_from_1",
         "b_from_2", "c_from_2", "post_lib1", "post_lib2", "-o", "a.out"]
    ]


def test_linker_inheriting() -> None:
    """
    Tests library argument pass-through from compiler to wrapper.
    """
    compiler = FortranCompiler("some Fortran compiler", 'sfc', 'some',
                               r'([\d.]+)')
    compiler_linker = Linker(compiler)
    wrapper = Mpif90(compiler)
    wrapper_linker = Linker(wrapper)

    compiler_linker.add_lib_flags("lib_a", ["a_from_1"])
    assert compiler_linker.get_lib_flags("lib_a") == ["a_from_1"]

    with raises(RuntimeError) as err:
        wrapper_linker.get_lib_flags("does_not_exist")
    assert str(err.value) == "Unknown library name: 'does_not_exist'"


def test_linker_profile_flags_inheriting(stub_c_compiler):
    """
    Tests nested compiler and nested linker with inherited profiling flags.
    """
    stub_c_compiler_wrapper = CompilerWrapper(name="stub_c_compiler_wrapper",
                                              compiler=stub_c_compiler,
                                              exec_name="exec_name")
    linker = Linker(stub_c_compiler_wrapper)
    linker_wrapper = Linker(stub_c_compiler_wrapper, linker=linker)

    count = 0
    for compiler in [stub_c_compiler, stub_c_compiler_wrapper]:
        compiler.define_profile("base")
        compiler.define_profile("derived", "base")
        compiler.add_flags(f"-f{count}", "base")
        compiler.add_flags(f"-f{count+1}", "derived")
        count += 2

    # One set f0-f3 from the compiler wrapper, one from the wrapped linker
    assert (linker_wrapper.get_profile_flags("derived") ==
            ["-f0", "-f1", "-f2", "-f3", "-f0", "-f1", "-f2", "-f3"])


def test_linker_profile_modes(stub_linker):
    '''Test that defining a profile mode in a linker will also define
    the same modes in post- and pre-flags

    ToDo: Monkeying with internal state.
    '''

    # Make sure that we get the expected errors at the start:
    with raises(KeyError) as err:
        stub_linker._pre_lib_flags["base"]
    assert "Profile 'base' is not defined" in str(err.value)
    with raises(KeyError) as err:
        stub_linker._post_lib_flags["base"]
    assert "Profile 'base' is not defined" in str(err.value)

    stub_linker.define_profile("base")
    assert stub_linker._pre_lib_flags["base"] == []
    assert "base" not in stub_linker._pre_lib_flags._inherit_from
    assert stub_linker._post_lib_flags["base"] == []
    assert "base" not in stub_linker._post_lib_flags._inherit_from

    stub_linker.define_profile("full-debug", "base")
    assert stub_linker._pre_lib_flags["full-debug"] == []
    assert stub_linker._pre_lib_flags._inherit_from["full-debug"] == "base"
    assert stub_linker._post_lib_flags["full-debug"] == []
    assert stub_linker._post_lib_flags._inherit_from["full-debug"] == "base"

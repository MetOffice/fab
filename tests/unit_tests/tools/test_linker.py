##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the linker implementation.
'''

from pathlib import Path
from unittest import mock
import warnings

import pytest

from fab.tools import (Category, Linker, ToolRepository)


def test_linker(mock_c_compiler, mock_fortran_compiler):
    '''Test the linker constructor.'''

    assert mock_c_compiler.category == Category.C_COMPILER
    assert mock_c_compiler.name == "mock_c_compiler"

    linker = Linker(mock_c_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-mock_c_compiler"
    assert linker.exec_name == "mock_c_compiler.exe"
    assert linker.suite == "suite"
    assert linker.flags == []
    assert linker.output_flag == "-o"

    assert mock_fortran_compiler.category == Category.FORTRAN_COMPILER
    assert mock_fortran_compiler.name == "mock_fortran_compiler"

    linker = Linker(mock_fortran_compiler)
    assert linker.category == Category.LINKER
    assert linker.name == "linker-mock_fortran_compiler"
    assert linker.exec_name == "mock_fortran_compiler.exe"
    assert linker.suite == "suite"
    assert linker.flags == []


@pytest.mark.parametrize("mpi", [True, False])
def test_linker_mpi(mock_c_compiler, mpi):
    '''Test that linker wrappers handle MPI as expected.'''

    mock_c_compiler._mpi = mpi
    linker = Linker(mock_c_compiler)
    assert linker.mpi == mpi

    wrapped_linker = Linker(mock_c_compiler, linker=linker)
    assert wrapped_linker.mpi == mpi


@pytest.mark.parametrize("openmp", [True, False])
def test_linker_openmp(mock_c_compiler, openmp):
    '''Test that linker wrappers handle openmp as expected. Note that
    a compiler detects support for OpenMP by checking if an openmp flag
    is defined.
    '''

    if openmp:
        mock_c_compiler._openmp_flag = "-some-openmp-flag"
    else:
        mock_c_compiler._openmp_flag = ""
    linker = Linker(compiler=mock_c_compiler)
    assert linker.openmp == openmp

    wrapped_linker = Linker(mock_c_compiler, linker=linker)
    assert wrapped_linker.openmp == openmp


def test_linker_gets_ldflags(mock_c_compiler):
    """Tests that the linker retrieves env.LDFLAGS"""
    with mock.patch.dict("os.environ", {"LDFLAGS": "-lm"}):
        linker = Linker(compiler=mock_c_compiler)
    assert "-lm" in linker.flags


def test_linker_check_available(mock_c_compiler):
    '''Tests the is_available functionality.'''

    # First test when a compiler is given. The linker will call the
    # corresponding function in the compiler:
    linker = Linker(mock_c_compiler)
    with mock.patch('fab.tools.compiler.Compiler.get_version',
                    return_value=(1, 2, 3)):
        assert linker.check_available()

    # Then test the usage of a linker wrapper. The linker will call the
    # corresponding function in the wrapper linker:
    wrapped_linker = Linker(mock_c_compiler, linker=linker)
    with mock.patch('fab.tools.compiler.Compiler.get_version',
                    return_value=(1, 2, 3)):
        assert wrapped_linker.check_available()


def test_linker_check_unavailable(mock_c_compiler):
    '''Tests the is_available functionality.'''
    # assume the tool does not exist, check_available
    # will return False (and not raise an exception)
    linker = Linker(mock_c_compiler)
    with mock.patch('fab.tools.compiler.Compiler.get_version',
                    side_effect=RuntimeError("")):
        assert linker.check_available() is False


# ====================
# Managing lib flags:
# ====================
def test_linker_get_lib_flags(mock_linker):
    """Linker should provide a map of library names, each leading to a list of
    linker flags
    """
    # netcdf flags are built in to the mock linker
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-lnetcdff", "-lnetcdf"]


def test_linker_get_lib_flags_unknown(mock_c_compiler):
    """Linker should raise an error if flags are requested for a library
    that is unknown.
    """
    linker = Linker(compiler=mock_c_compiler)
    with pytest.raises(RuntimeError) as err:
        linker.get_lib_flags("unknown")
    assert "Unknown library name: 'unknown'" in str(err.value)


def test_linker_add_lib_flags(mock_c_compiler):
    """Linker should provide a way to add a new set of flags for a library"""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("xios", ["-L", "xios/lib", "-lxios"])

    # Make sure we can get it back. The order should be maintained.
    result = linker.get_lib_flags("xios")
    assert result == ["-L", "xios/lib", "-lxios"]


def test_linker_add_lib_flags_overwrite_defaults(mock_linker):
    """Linker should provide a way to replace the default flags for
    a library"""

    # Initially we have the default netcdf flags
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-lnetcdff", "-lnetcdf"]

    # Replace them with another set of flags.
    warn_message = 'Replacing existing flags for library netcdf'
    with pytest.warns(UserWarning, match=warn_message):
        mock_linker.add_lib_flags(
            "netcdf", ["-L", "netcdf/lib", "-lnetcdf"])

    # Test that we can see our custom flags
    result = mock_linker.get_lib_flags("netcdf")
    assert result == ["-L", "netcdf/lib", "-lnetcdf"]


def test_linker_add_lib_flags_overwrite_silent(mock_linker):
    """Linker should provide the option to replace flags for a library without
    generating a warning
    """

    # Initially we have the default netcdf flags
    mock_linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    assert mock_linker.get_lib_flags("customlib") == ["-lcustom", "-jcustom"]

    # Replace them with another set of flags.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        mock_linker.add_lib_flags("customlib", ["-t", "-b"],
                                  silent_replace=True)

    # Test that we can see our custom flags
    result = mock_linker.get_lib_flags("customlib")
    assert result == ["-t", "-b"]


# ====================
# Linking:
# ====================
def test_linker_c(mock_c_compiler):
    '''Test the link command line when no additional libraries are
    specified.'''

    linker = Linker(compiler=mock_c_compiler)
    # Add a library to the linker, but don't use it in the link step
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ["mock_c_compiler.exe", "a.o", "-o", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_c_with_libraries(mock_c_compiler):
    """Test the link command line when additional libraries are specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=True)
    # The order of the 'libs' list should be maintained
    link_run.assert_called_with(
        ["-fopenmp", "a.o", "-lcustom", "-jcustom", "-o", "a.out"])


def test_linker_c_with_libraries_and_post_flags(mock_c_compiler):
    """Test the link command line when a library and additional flags are
    specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_post_lib_flags(["-extra-flag"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=False)
    link_run.assert_called_with(
        ["a.o", "-lcustom", "-jcustom", "-extra-flag", "-o", "a.out"])


def test_linker_c_with_libraries_and_pre_flags(mock_c_compiler):
    """Test the link command line when a library and additional flags are
    specified."""
    linker = Linker(compiler=mock_c_compiler)
    linker.add_lib_flags("customlib", ["-lcustom", "-jcustom"])
    linker.add_pre_lib_flags(["-L", "/common/path/"])

    with mock.patch.object(linker, "run") as link_run:
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=False)
    link_run.assert_called_with(
        ["a.o", "-L", "/common/path/", "-lcustom", "-jcustom", "-o", "a.out"])


def test_linker_c_with_unknown_library(mock_c_compiler):
    """Test the link command raises an error when unknow libraries are
    specified.
    """
    linker = Linker(compiler=mock_c_compiler)\

    with pytest.raises(RuntimeError) as err:
        # Try to use "customlib" when we haven't added it to the linker
        linker.link(
            [Path("a.o")], Path("a.out"), libs=["customlib"], openmp=True)

    assert "Unknown library name: 'customlib'" in str(err.value)


def test_compiler_linker_add_compiler_flag(mock_c_compiler):
    '''Test that a flag added to the compiler will be automatically
    added to the link line (even if the flags are modified after creating the
    linker ... in case that the user specifies additional flags after creating
    the linker).'''

    linker = Linker(compiler=mock_c_compiler)
    mock_c_compiler.flags.append("-my-flag")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        linker.link([Path("a.o")], Path("a.out"), openmp=False)
    tool_run.assert_called_with(
        ['mock_c_compiler.exe', '-my-flag', 'a.o', '-o', 'a.out'],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_all_flag_types(mock_c_compiler):
    """Make sure all possible sources of linker flags are used in the right
    order"""

    # Environment variables for both the linker
    with mock.patch.dict("os.environ", {"LDFLAGS": "-ldflag"}):
        linker = Linker(compiler=mock_c_compiler)

    mock_c_compiler.add_flags(["-compiler-flag1", "-compiler-flag2"])
    linker.add_flags(["-linker-flag1", "-linker-flag2"])
    linker.add_pre_lib_flags(["-prelibflag1", "-prelibflag2"])
    linker.add_lib_flags("customlib1", ["-lib1flag1", "lib1flag2"])
    linker.add_lib_flags("customlib2", ["-lib2flag1", "lib2flag2"])
    linker.add_post_lib_flags(["-postlibflag1", "-postlibflag2"])

    mock_result = mock.Mock(returncode=0)
    with mock.patch("fab.tools.tool.subprocess.run",
                    return_value=mock_result) as tool_run:
        linker.link([
            Path("a.o")], Path("a.out"),
            libs=["customlib2", "customlib1"],
            openmp=True)

    tool_run.assert_called_with([
        "mock_c_compiler.exe",
        "-ldflag", "-linker-flag1", "-linker-flag2",
        "-compiler-flag1", "-compiler-flag2",
        "-fopenmp",
        "a.o",
        "-prelibflag1", "-prelibflag2",
        "-lib2flag1", "lib2flag2",
        "-lib1flag1", "lib1flag2",
        "-postlibflag1", "-postlibflag2",
        "-o", "a.out"],
        capture_output=True, env=None, cwd=None, check=False)


def test_linker_nesting(mock_c_compiler):
    """Make sure all possible sources of linker flags are used in the right
    order"""

    linker1 = Linker(compiler=mock_c_compiler)
    linker1.add_pre_lib_flags(["pre_lib1"])
    linker1.add_lib_flags("lib_a", ["a_from_1"])
    linker1.add_lib_flags("lib_c", ["c_from_1"])
    linker1.add_post_lib_flags(["post_lib1"])
    linker2 = Linker(mock_c_compiler, linker=linker1)
    linker2.add_pre_lib_flags(["pre_lib2"])
    linker2.add_lib_flags("lib_b", ["b_from_2"])
    linker2.add_lib_flags("lib_c", ["c_from_2"])
    linker1.add_post_lib_flags(["post_lib2"])

    mock_result = mock.Mock(returncode=0)
    with mock.patch("fab.tools.tool.subprocess.run",
                    return_value=mock_result) as tool_run:
        linker2.link(
            [Path("a.o")], Path("a.out"),
            libs=["lib_a", "lib_b", "lib_c"],
            openmp=True)
    tool_run.assert_called_with(["mock_c_compiler.exe", "-fopenmp",
                                 "a.o", "pre_lib2", "pre_lib1", "a_from_1",
                                 "b_from_2", "c_from_2",
                                 "post_lib1", "post_lib2", "-o", "a.out"],
                                capture_output=True, env=None, cwd=None,
                                check=False)


def test_linker_inheriting():
    '''Make sure that libraries from a wrapper compiler will be
    available for a wrapper.
    '''
    tr = ToolRepository()
    linker_gfortran = tr.get_tool(Category.LINKER, "linker-gfortran")
    linker_mpif90 = tr.get_tool(Category.LINKER, "linker-mpif90-gfortran")

    linker_gfortran.add_lib_flags("lib_a", ["a_from_1"])
    assert linker_mpif90.get_lib_flags("lib_a") == ["a_from_1"]

    with pytest.raises(RuntimeError) as err:
        linker_mpif90.get_lib_flags("does_not_exist")
    assert "Unknown library name: 'does_not_exist'" in str(err.value)

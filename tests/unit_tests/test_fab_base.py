##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the FabBase class
"""
import os
import sys

import pytest
from unittest import mock

from pytest_subprocess.fake_process import FakeProcess

from fab.build_config import AddFlags
from fab.fab_base import FabBase
from fab.tools import Category, ToolRepository


@pytest.fixture(scope="function", autouse=True)
def setup_tool_repository(stub_fortran_compiler, stub_c_compiler,
                          stub_linker):
    '''
    This sets up a ToolRepository that allows the Baf base-class
    to proceed without raising errors. This fixture is automatically
    executed for any test in this file.
    '''
    # Make sure we always get a new ToolRepo to be not affected by
    # other tests:
    ToolRepository._singleton = None

    # Remove all compiler and linker, so we get results independent
    # of the software available on the platform this test is running
    tr = ToolRepository()
    for category in [Category.C_COMPILER, Category.FORTRAN_COMPILER,
                     Category.LINKER]:
        tr[category] = []

    # Add a compilers and linkers, and mark them all as available,
    # as well as supporting MPI and OpenMP (to reduce number of
    # command line options required).
    for tool in [stub_c_compiler, stub_fortran_compiler, stub_linker]:
        tool._mpi = True
        tool._openmp_flag = "-some-openmp-flag"
        tool._is_available = True
        tool._version = (1, 2, 3)
        tr.add_tool(tool)

    # Remove all environment variables to make sure FC etc does not
    # influence results
    with mock.patch.dict(os.environ, clear=True):
        yield


def test_constructor() -> None:
    '''
    Tests constructor.
    '''
    with pytest.raises(ValueError) as err:
        _ = FabBase(name="test_name", link_target="wrong")
    assert ("Invalid parameter 'wrong', must be one of 'executable, "
            "static-library, shared-library'." in str(err.value))


def test_help(monkeypatch, capsys) -> None:
    '''
    Tests that help is printed as expected.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "-h"])
    with pytest.raises(SystemExit):
        _ = FabBase(name="test-help")
    out, _ = capsys.readouterr()
    assert "A Fab-based build system." in out


@pytest.mark.parametrize("arg", [(["--site", "testsite"], "site"),
                                 (["--platform", "testplatf"], "platform"),
                                 ])
def test_args(change_into_tmpdir, monkeypatch, arg) -> None:
    '''
    Tests that command line arguments are accessible as expected.
    '''
    flag_list, attribute = arg
    monkeypatch.setattr(sys, "argv", ["fab_base.py"]+flag_list)
    fab_base = FabBase(name="test-help")
    assert getattr(fab_base.args, attribute) == flag_list[1]


def test_arg_error(change_into_tmpdir, monkeypatch) -> None:
    '''
    Tests handling of errors in the command line.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--host", "invalid"])
    with pytest.raises(RuntimeError) as err:
        _ = FabBase(name="test-help")
    assert ("Invalid host directive 'invalid'. Must be 'cpu' or 'gpu'." ==
            str(err.value))


@pytest.mark.parametrize("arg", [(["--fflags", "fflag"], "fflags"),
                                 (["--cflags", "cflag"], "cflags"),
                                 (["--ldflags", "ldflag"], "ldflags"),
                                 ])
def test_compiler_flags(change_into_tmpdir, monkeypatch, arg) -> None:
    '''
    Tests that command line arguments are accessible as expected.
    '''
    flag_list, attribute = arg
    monkeypatch.setattr(sys, "argv", ["fab_base.py"]+flag_list)
    fab_base = FabBase(name="test-help")
    assert getattr(fab_base.args, attribute) == flag_list[1]


def test_available_compilers(monkeypatch, capsys) -> None:
    '''
    Tests the list of available compilers.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--available-compilers"])
    with pytest.raises(SystemExit):
        _ = FabBase(name="test-help")
    out, _ = capsys.readouterr()
    assert "----- Available compiler and linkers -----" in out
    assert "FortranCompiler - some Fortran compiler: sfc" in out
    assert "CCompiler - some C compiler: scc" in out
    assert "Linker - sln: scc" in out


def test_root_symbol(monkeypatch) -> None:
    '''
    Tests setting the root symbol(s).
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    fab_base = FabBase(name="test-help")

    # Set a single root symbol
    fab_base.set_root_symbol("root1")
    assert fab_base.root_symbol == ["root1"]

    fab_base.set_root_symbol(["root1", "root2"])
    assert fab_base.root_symbol == ["root1", "root2"]


def test_profile_default(monkeypatch) -> None:
    '''
    Check that a default is picked if no profile is specified. The
    testing config specifies 'default-profile' as default profile.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    fab_base = FabBase(name="test-help")
    assert fab_base.args.profile == "default-profile"


def test_profile_command_line(monkeypatch) -> None:
    '''
    Tests explicitly setting the profile
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--profile",
                                      "full-debug"])
    fab_base = FabBase(name="test-help")
    assert fab_base.args.profile == "full-debug"


def test_profile_invalid(monkeypatch) -> None:
    '''
    Tests trying to set an invalid profile:
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--profile", "invalid"])
    with pytest.raises(RuntimeError) as err:
        _ = FabBase(name="test-help")
    assert "Invalid profile 'invalid" == str(err.value)


def test_suite_no_compiler(monkeypatch) -> None:
    '''
    Tests setting a compiler suite, and no compiler etc. That should
    set the compiler selected in args to None
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--suite", "stub"])
    fab_base = FabBase(name="test-help")

    assert fab_base.args.cc is None
    assert fab_base.args.fc is None
    assert fab_base.args.ld is None


def test_suite_compiler(monkeypatch) -> None:
    '''
    Tests setting a compiler suite, and select a compiler. That should
    set the compiler to the selected arg, everything else is None
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--suite", "stub",
                                      "-fc", "sfc"])
    fab_base = FabBase(name="test-help")

    assert fab_base.args.cc is None
    assert fab_base.args.fc == "sfc"
    assert fab_base.args.ld is None


def test_compiler_no_arg(monkeypatch) -> None:
    '''
    Tests compiler setting without an explicit argument:
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    fab_base = FabBase(name="test-help")

    assert fab_base.args.cc is None
    assert fab_base.args.fc is None
    assert fab_base.args.ld is None


@pytest.mark.parametrize("env", [{"FC": "sfc"},
                                 {"CC": "scc"},
                                 {"LD": "sln"}])
def test_compiler_env_variable(monkeypatch, env) -> None:
    '''
    Tests compiler setting based on an environment variable
    '''
    with mock.patch.dict("os.environ", env):
        monkeypatch.setattr(sys, "argv", ["fab_base.py"])
        fab_base = FabBase(name="test-help")

        assert fab_base.args.fc == env.get("FC", None)
        assert fab_base.args.cc == env.get("CC", None)
        assert fab_base.args.ld == env.get("LD", None)


def test_preprocessor_flags(monkeypatch) -> None:
    '''
    Tests setting of preprocessor flags.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    fab_base = FabBase(name="test-help")
    # Initially there should be no flags
    assert fab_base.preprocess_flags_common == []
    assert fab_base.preprocess_flags_path == []

    # Support a single string as flag:
    fab_base.add_preprocessor_flags("-f1")
    assert fab_base.preprocess_flags_common == ["-f1"]
    assert fab_base.preprocess_flags_path == []

    # Add a list of flags
    fab_base.add_preprocessor_flags(["-f2", "-f3"])
    assert fab_base.preprocess_flags_common == ["-f1", "-f2", "-f3"]
    assert fab_base.preprocess_flags_path == []

    # Support a single AddFlag as flag:
    af1 = AddFlags("some_path", ["-a1"])
    fab_base.add_preprocessor_flags(af1)
    assert fab_base.preprocess_flags_common == ["-f1", "-f2", "-f3"]
    assert fab_base.preprocess_flags_path == [af1]

    # Add a list of flags
    af2 = AddFlags("some_path", ["-a2"])
    af3 = AddFlags("some_path", ["-a3"])
    fab_base.add_preprocessor_flags([af2, af3])
    assert fab_base.preprocess_flags_common == ["-f1", "-f2", "-f3"]
    assert fab_base.preprocess_flags_path == [af1, af2, af3]

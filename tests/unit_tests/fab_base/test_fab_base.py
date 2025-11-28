##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the FabBase class
"""
import inspect
import os
from pathlib import Path
import sys
from unittest import mock

import pytest

from fab.build_config import AddFlags
from fab.fab_base.fab_base import FabBase
from fab.tools.category import Category
from fab.tools.tool_repository import ToolRepository


@pytest.fixture(scope="function", autouse=True)
def setup_tool_repository(stub_fortran_compiler, stub_c_compiler,
                          stub_linker):
    '''
    This sets up a ToolRepository that allows the Baf base-class
    to proceed without raising errors. This fixture is automatically
    executed for any test in this file.
    '''
    # pylint: disable=protected-access
    # Make sure we always get a new ToolRepository to be not affected by
    # other tests:
    ToolRepository._singleton = None

    # Remove all compiler and linker, so we get results independent
    # of the software available on the platform this test is running
    tr = ToolRepository()
    for category in [Category.C_COMPILER, Category.FORTRAN_COMPILER,
                     Category.LINKER]:
        tr[category] = []

    # Add compilers and linkers, and mark them all as available,
    # as well as supporting MPI and OpenMP (to reduce number of
    # command line options required).
    for tool in [stub_c_compiler, stub_fortran_compiler, stub_linker]:
        tool._mpi = True
        tool._openmp_flag = "-some-openmp-flag"
        tool._is_available = True
        tool._version = (1, 2, 3)
        tr.add_tool(tool)

    # Remove all environment variables to make sure FC etc (which will
    # be picked up by FabBase) do not influence results
    with mock.patch.dict(os.environ, clear=True):
        yield

    # Now reset the tool repository, so that other tests get
    # the expected state.
    ToolRepository._singleton = None


def test_constructor(monkeypatch) -> None:
    '''
    Tests constructor.
    '''
    with pytest.raises(ValueError) as err:
        _ = FabBase(name="test_name", link_target="wrong")
    assert ("Invalid parameter 'wrong', must be one of 'executable, "
            "static-library, shared-library'." in str(err.value))

    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    fab_base = FabBase(name="test_name", link_target="executable")

    # Check other settings and functions
    # pylint: disable=use-implicit-booleaness-not-comparison
    assert fab_base.get_linker_flags() == []


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
                                 (["--platform", "testplatform"], "platform"),
                                 ])
def test_site_platform(monkeypatch, arg) -> None:
    '''
    Tests that command line arguments for site and platform work
    '''
    flag_list, attribute = arg
    monkeypatch.setattr(sys, "argv", ["fab_base.py"]+flag_list)
    fab_base = FabBase(name="test-help")
    assert getattr(fab_base, attribute) == flag_list[1]


def test_arg_error(monkeypatch) -> None:
    '''
    Tests handling of errors in the command line.
    '''
    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--host", "invalid"])
    with pytest.raises(RuntimeError) as err:
        _ = FabBase(name="test-help")
    assert ("Invalid host directive 'invalid'. Must be 'cpu' or 'gpu'." ==
            str(err.value))


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
    # pylint: disable=use-implicit-booleaness-not-comparison
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


def test_workspace(monkeypatch, change_into_tmpdir) -> None:
    '''
    Tests setting the working space on the command line
    '''

    tmpdir = change_into_tmpdir
    new_workspace = "new_workspace"
    new_workspace = tmpdir / new_workspace

    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--fab-workspace",
                                      str(new_workspace)])
    fab_base = FabBase(name="root_symbol_does_not_exit")

    # Since FabBase itself requests Fab to find programs, but there
    # is none, Fab will abort in the linking step (missing targets).
    # Note that the project directories are only created once
    # build is called.
    with pytest.raises(ValueError) as err:
        fab_base.build()
    assert "No target objects defined, linking aborted" in str(err.value)

    # Check that the project workspace is as expected:
    project_dir = fab_base.project_workspace
    assert (f"{new_workspace}/root_symbol_does_not_exit-default-profile-"
            f"some_Fortran_compiler" in str(project_dir))


@pytest.mark.parametrize("arg", [(["--fflags", "fflag"], "fflags"),
                                 (["--cflags", "cflag"], "cflags"),
                                 (["--ldflags", "ldflag"], "ldflags"),
                                 ])
def test_compiler_flags(monkeypatch, arg) -> None:
    '''
    Tests that command line arguments are accessible as expected.
    '''
    flag_list, attribute = arg
    monkeypatch.setattr(sys, "argv", ["fab_base.py"]+flag_list)
    fab_base = FabBase(name="test-help")
    assert getattr(fab_base.args, attribute) == flag_list[1]
    if flag_list[0] == "--fflags":
        assert fab_base.fortran_compiler_flags_commandline == [flag_list[1]]
    elif flag_list[0] == "--cflags":
        assert fab_base.c_compiler_flags_commandline == [flag_list[1]]
    elif flag_list[0] == "--ldflags":
        assert fab_base.linker_flags_commandline == [flag_list[1]]


def test_site_specific_outside_dir(monkeypatch) -> None:
    '''
    Tests site-specific settings if the call is initiated from a different
    directory. In this case, the `cwd` and `cwd/site_specific` should
    be added to the Python path (to allow importing the site-specific
    settings.
    '''
    this_dir = Path(__file__).parent
    old_path = sys.path[:]
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    _ = FabBase(name="test-help")
    assert sys.path[2:] == old_path
    assert str(this_dir / "site_specific") in sys.path[0]
    assert str(this_dir) in sys.path[1]


def test_site_specific_inside_dir(monkeypatch) -> None:
    '''
    Tests site-specific settings if the call is initiated from the
    same directory as FabBase. This is done by patching inspect
    to return an empty list. In this case, only one directory
    should be added the search path
    '''
    old_path = sys.path[:]
    monkeypatch.setattr(sys, "argv", ["fab_base.py"])
    monkeypatch.setattr(inspect, "stack", lambda: [])
    _ = FabBase(name="test-help")
    assert sys.path[1:] == old_path
    assert "site_specific" == sys.path[0]


def test_build_binary(monkeypatch) -> None:
    '''
    Tests an actual trivial build. We patch all fab functions called
    by the FabBase class, so no actual work will be done (e.g. we don't
    need compiler, rsync)
    '''

    monkeypatch.setattr(sys, "argv", ["fab_base.py", "--fflags",
                                      "some-fflags"])

    fab_base = FabBase(name="test")

    # We need to patch a lot of Fab functions (to avoid dependencies
    # on the runtime environment):
    mocks = {}
    for function_name in ["grab_folder", "find_source_files",
                          "preprocess_c", "preprocess_fortran",
                          "compile_fortran", "compile_c", "analyse"]:
        patcher = mock.patch(f"fab.fab_base.fab_base.{function_name}")
        mocks[function_name] = (patcher, patcher.start())

    with pytest.raises(ValueError) as err:
        fab_base.build()
    assert "No target objects defined, linking aborted" in str(err.value)

    mocks["grab_folder"][0].stop()
    mocks["grab_folder"][1].assert_called_once_with(
        fab_base.config, src=".")

    mocks["find_source_files"][0].stop()
    mocks["find_source_files"][1].assert_called_once_with(
        fab_base.config, path_filters=None)

    mocks["preprocess_fortran"][0].stop()
    mocks["preprocess_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["compile_fortran"][0].stop()
    mocks["compile_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=['some-fflags'], path_flags=[])

    mocks["compile_c"][0].stop()
    mocks["compile_c"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    # When using FabBase directly (as we do here), it will request
    # Fab to search for all programs to support zero-config. Check
    # that indeed this flag is passed in.
    mocks["analyse"][0].stop()
    mocks["analyse"][1].assert_called_once_with(
        fab_base.config, find_programs=True, ignore_dependencies=None)


def test_build_static_lib(monkeypatch) -> None:
    '''
    Tests an actual trivial build. We patch all fab functions called
    by the FabBase class, so no actual work will be done (e.g. we don't
    need compiler, rsync)
    '''

    monkeypatch.setattr(sys, "argv", ["fab_base.py"])

    fab_base = FabBase(name="test", link_target="static-library")
    workspace = fab_base.project_workspace

    # We need to patch a lot of Fab functions (to avoid dependencies
    # on the runtime environment):
    mocks = {}
    for function_name in ["grab_folder", "find_source_files", "preprocess_c",
                          "preprocess_fortran", "compile_fortran",
                          "compile_c", "analyse", "archive_objects"]:
        patcher = mock.patch(f"fab.fab_base.fab_base.{function_name}")
        mocks[function_name] = (patcher, patcher.start())

    fab_base.build()

    mocks["grab_folder"][0].stop()
    mocks["grab_folder"][1].assert_called_once_with(
        fab_base.config, src=".")

    mocks["find_source_files"][0].stop()
    mocks["find_source_files"][1].assert_called_once_with(
        fab_base.config, path_filters=None)

    mocks["preprocess_fortran"][0].stop()
    mocks["preprocess_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["compile_fortran"][0].stop()
    mocks["compile_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["compile_c"][0].stop()
    mocks["compile_c"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["analyse"][0].stop()
    mocks["analyse"][1].assert_called_once_with(
        fab_base.config, root_symbol=None, ignore_dependencies=None)

    mocks["archive_objects"][0].stop()
    mocks["archive_objects"][1].assert_called_once_with(
        fab_base.config, output_fpath=str(workspace / 'libtest.a'))


def test_build_shared_lib(monkeypatch) -> None:
    '''
    Tests an actual trivial build. We patch all fab functions called
    by the FabBase class, so no actual work will be done (e.g. we don't
    need compiler, rsync)
    '''

    monkeypatch.setattr(sys, "argv", ["fab_base.py"])

    fab_base = FabBase(name="test", link_target="shared-library")
    workspace = fab_base.project_workspace

    # We need to patch a lot of Fab functions (to avoid dependencies
    # on the runtime environment):
    mocks = {}
    for function_name in ["grab_folder", "find_source_files", "preprocess_c",
                          "preprocess_fortran", "compile_fortran",
                          "compile_c", "analyse", "link_shared_object"]:
        patcher = mock.patch(f"fab.fab_base.fab_base.{function_name}")
        mocks[function_name] = (patcher, patcher.start())

    fab_base.build()

    mocks["grab_folder"][0].stop()
    mocks["grab_folder"][1].assert_called_once_with(
        fab_base.config, src=".")

    mocks["find_source_files"][0].stop()
    mocks["find_source_files"][1].assert_called_once_with(
        fab_base.config, path_filters=None)

    mocks["preprocess_fortran"][0].stop()
    mocks["preprocess_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["compile_fortran"][0].stop()
    mocks["compile_fortran"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["compile_c"][0].stop()
    mocks["compile_c"][1].assert_called_once_with(
        fab_base.config, common_flags=[], path_flags=[])

    mocks["analyse"][0].stop()
    mocks["analyse"][1].assert_called_once_with(
        fab_base.config, root_symbol=None, ignore_dependencies=None)

    mocks["link_shared_object"][0].stop()
    mocks["link_shared_object"][1].assert_called_once_with(
        fab_base.config, output_fpath=str(workspace / 'libtest.so'),
        flags=[])

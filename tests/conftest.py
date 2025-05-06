##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fixtures and helpers for testing.
"""
from pathlib import Path
from typing import Dict, List, Optional

from pytest import fixture
from pytest_subprocess.fake_process import FakeProcess, ProcessRecorder

from fab.build_config import BuildConfig
from fab.tools.compiler import CCompiler, FortranCompiler
from fab.tools.linker import Linker
from fab.tools.tool_box import ToolBox


def not_found_callback(process):
    """
    Raises a FileNotFoundError.

    This is useful for generating this specific error when mocking
    subprocesses.
    """
    process.returncode = 1
    raise FileNotFoundError("Executable file missing")


def call_list(fake_process: FakeProcess) -> List[List[str]]:
    """
    Converts FakeProcess calls to strings.

    :returns: List of argument strings per call.
    """
    result: List[List[str]] = []
    for call in fake_process.calls:
        result.append([str(arg) for arg in call])
    return result


def arg_list(record: ProcessRecorder) -> List[Dict[str, str]]:
    """
    Converts ProcessRecorder calls to subprocess arguments.

    This gives access to e.g. pwd specified with each call.

    :returns: Dictionary of argument passed to subprocess per call.
    """
    result: List[Dict[str, str]] = []
    for call in record.calls:
        if call.kwargs is None:
            args = {}
        else:
            args = {key: str(value) for key, value in call.kwargs.items()}
        result.append(args)
    return result


class ExtendedRecorder:
    """
    Adds convenience functionality to ProcessRecorder.
    """
    def __init__(self, recorder: ProcessRecorder):
        self.recorder = recorder

    def invocations(self) -> List[List[str]]:
        """
        Lists invocations as simple string lists.
        """
        calls = []
        for call in self.recorder.calls:
            calls.append([str(arg) for arg in call.args])
        return calls

    def extras(self) -> List[Dict[str, Optional[str]]]:
        """
        Lists arguments passed to subprocess.

        This allows .e.g. pwd to be seen, if set.
        """
        args: List[Dict[str, Optional[str]]] = []
        for call in self.recorder.calls:
            things: Dict[str, Optional[str]] = {}
            if call.kwargs is None:
                continue
            for key, value in call.kwargs.items():
                if value is None:
                    things[key] = None
                else:
                    if key in ('stdout', 'stderr') and value == -1:
                        things[key] = None
                    else:
                        things[key] = str(value)
            args.append(things)
        return args


@fixture(scope='function')
def subproc_record(fake_process: FakeProcess) -> ExtendedRecorder:
    """
    Mocks the 'subprocess' module and returns a recorder of commands issued.
    """
    fake_process.keep_last_process(True)
    return ExtendedRecorder(fake_process.register([FakeProcess.any()]))


@fixture(scope='function')
def stub_fortran_compiler() -> FortranCompiler:
    """
    Provides a minimal Fortran compiler.
    """
    compiler = FortranCompiler('some Fortran compiler', 'sfc', 'stub',
                               r'([\d.]+)', openmp_flag='-omp',
                               module_folder_flag='-mods')
    return compiler


@fixture(scope='function')
def stub_c_compiler() -> CCompiler:
    """
    Provides a minial C compiler.
    """
    compiler = CCompiler("some C compiler", "scc", "stub",
                         version_regex=r"([\d.]+)", openmp_flag='-omp')
    return compiler


@fixture(scope='function')
def stub_linker(stub_c_compiler) -> Linker:
    """
    Provides a minimal linker.
    """
    linker = Linker(stub_c_compiler, None, 'sln')
    return linker


def return_true():
    """
    Returns true.

    Useful when monkeypatching methods.
    """
    return True


@fixture(scope='function')
def stub_tool_box(stub_fortran_compiler,
                  stub_c_compiler,
                  stub_linker,
                  monkeypatch) -> ToolBox:
    """
    Provides a minimal toolbox containing just Fortran and C compilers and a
    linker.
    """
    monkeypatch.setattr(stub_fortran_compiler, 'check_available', return_true)
    monkeypatch.setattr(stub_c_compiler, 'check_available', return_true)
    monkeypatch.setattr(stub_linker, 'check_available', return_true)
    toolbox = ToolBox()
    toolbox.add_tool(stub_fortran_compiler)
    toolbox.add_tool(stub_c_compiler)
    toolbox.add_tool(stub_linker)
    return toolbox


@fixture(scope='function')
def stub_configuration(stub_tool_box: ToolBox, tmp_path: Path) -> BuildConfig:
    """
    Provides a minimal configuration with stub compilers.
    """
    return BuildConfig("Stub config", stub_tool_box,
                       fab_workspace=tmp_path / 'fab')

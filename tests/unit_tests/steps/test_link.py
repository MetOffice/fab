# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Exercises executable linkage step.
"""
from pathlib import Path

from pytest import warns, raises
from pytest_subprocess.fake_process import FakeProcess

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.parse.c import AnalysedC
from fab.parse.fortran import AnalysedFortran
from fab.steps.link import link_exe
from fab.tools.category import Category
from fab.tools.linker import Linker
from fab.tools.tool_box import ToolBox
from fab.tools.tool_repository import ToolRepository

from tests.conftest import call_list


def test_run(fake_process: FakeProcess,
             stub_fortran_compiler) -> None:
    """
    Tests linking an executable. Make sure the command
    is formed correctly.
    """

    version_command = ['sfc', '--version']
    fake_process.register(version_command, stdout='1.2.3')
    link_command = ['sfc', 'bar.o', 'foo.o',
                    '-L/my/lib', '-lmylib', '-fooflag', '-barflag',
                    '-o', '/fab/link_test/foo']
    fake_process.register(link_command, stdout='abc\ndef')

    linker = Linker(compiler=stub_fortran_compiler)
    linker.add_lib_flags('mylib', ['-L/my/lib', '-lmylib'])

    tool_box = ToolBox()
    tool_box.add_tool(stub_fortran_compiler)
    tool_box.add_tool(linker)

    config = BuildConfig('link_test', tool_box, fab_workspace=Path('/fab'),
                         mpi=False, openmp=False, multiprocessing=False)
    config.artefact_store[ArtefactSet.OBJECT_FILES] = \
        {'foo': {'foo.o', 'bar.o'}}

    with warns(UserWarning,
               match="_metric_send_conn not set, cannot send metrics"):
        link_exe(config, libs=['mylib'], flags=['-fooflag', '-barflag'])
    assert call_list(fake_process) == [version_command, link_command]


def test_run_select_linker_fortran(fake_process: FakeProcess,
                                   stub_c_compiler,
                                   stub_fortran_compiler,
                                   monkeypatch) -> None:
    """
    Tests that a Fortran compiler is picked when a Fortran main program
    is linked and no explicit linker is specified.
    """

    c_version_command = ['scc', '--version']
    fake_process.register(c_version_command, stdout='1.2.3')
    f_version_command = ['sfc', '--version']
    fake_process.register(f_version_command, stdout='1.2.3')
    link_command = ['sfc', 'bar.o', 'foo.o',
                    '-L/my/f-lib', '-lmylib-f', '-fooflag', '-barflag',
                    '-o', '/fab/link_test/foo']
    fake_process.register(link_command, stdout='abc\ndef')

    c_linker = Linker(compiler=stub_c_compiler)
    c_linker.add_lib_flags('mylib', ['-L/my/c-lib', '-lmylib-c'])
    f_linker = Linker(compiler=stub_fortran_compiler)
    f_linker.add_lib_flags('mylib', ['-L/my/f-lib', '-lmylib-f'])
    tr = ToolRepository()
    monkeypatch.setitem(tr, Category.FORTRAN_COMPILER, [stub_fortran_compiler])
    monkeypatch.setitem(tr, Category.C_COMPILER, [stub_c_compiler])
    monkeypatch.setitem(tr, Category.LINKER, [c_linker, f_linker])
    default_linker = tr.get_default(Category.LINKER, openmp=False,
                                    mpi=False, enforce_fortran_linker=False)

    # First ensure that by default we would get the C linker.
    assert default_linker is c_linker

    config = BuildConfig('link_test', ToolBox(), fab_workspace=Path('/fab'),
                         mpi=False, openmp=False, multiprocessing=False)
    a_f = AnalysedFortran(fpath=Path('/fab/foo.f90'),
                          file_deps={Path('/fab/foo.f90')},
                          file_hash=0,
                          program_defs=["foo"],
                          symbol_defs=["foo"])
    config.artefact_store[ArtefactSet.BUILD_TREES] = \
        {"foo": {a_f.fpath: a_f}}

    config.artefact_store[ArtefactSet.OBJECT_FILES] = \
        {'foo': {'foo.o', 'bar.o'}}

    with warns(UserWarning,
               match="_metric_send_conn not set, cannot send metrics"):
        link_exe(config, libs=['mylib'], flags=['-fooflag', '-barflag'])
    assert call_list(fake_process) == [c_version_command, f_version_command,
                                       link_command]


def test_run_select_linker_c(fake_process: FakeProcess,
                             stub_c_compiler,
                             stub_fortran_compiler,
                             monkeypatch) -> None:
    """
    Tests that a C compiler is picked when a C main program
    is linked and no explicit linker is specified.
    """

    c_version_command = ['scc', '--version']
    fake_process.register(c_version_command, stdout='1.2.3')
    f_version_command = ['sfc', '--version']
    fake_process.register(f_version_command, stdout='1.2.3')
    link_command = ['scc', 'bar.o', 'foo.o',
                    '-L/my/c-lib', '-lmylib-c', '-fooflag', '-barflag',
                    '-o', '/fab/link_test/foo']
    fake_process.register(link_command, stdout='abc\ndef')

    c_linker = Linker(compiler=stub_c_compiler)
    c_linker.add_lib_flags('mylib', ['-L/my/c-lib', '-lmylib-c'])
    f_linker = Linker(compiler=stub_fortran_compiler)
    f_linker.add_lib_flags('mylib', ['-L/my/f-lib', '-lmylib-f'])
    tr = ToolRepository()
    monkeypatch.setitem(tr, Category.FORTRAN_COMPILER, [stub_fortran_compiler])
    monkeypatch.setitem(tr, Category.C_COMPILER, [stub_c_compiler])
    monkeypatch.setitem(tr, Category.LINKER, [f_linker, c_linker])
    default_linker = tr.get_default(Category.LINKER, openmp=False,
                                    mpi=False, enforce_fortran_linker=True)

    # First ensure that by default we would get the C linker.
    assert default_linker is f_linker

    config = BuildConfig('link_test', ToolBox(), fab_workspace=Path('/fab'),
                         mpi=False, openmp=False, multiprocessing=False)
    a_c = AnalysedC(fpath=Path('/fab/foo.f90'),
                    file_deps={Path('/fab/foo.f90')},
                    file_hash=0,
                    symbol_defs=["main"])
    config.artefact_store[ArtefactSet.BUILD_TREES] = \
        {"foo": {a_c.fpath: a_c}}

    config.artefact_store[ArtefactSet.OBJECT_FILES] = \
        {'foo': {'foo.o', 'bar.o'}}

    with warns(UserWarning,
               match="_metric_send_conn not set, cannot send metrics"):
        link_exe(config, libs=['mylib'], flags=['-fooflag', '-barflag'])
    assert call_list(fake_process) == [f_version_command, c_version_command,
                                       link_command]


def test_no_targets(fake_process: FakeProcess,
                    stub_fortran_compiler) -> None:
    """
    Tests that a warning is issued if no definitions for linking
    an executable is available.
    """

    version_command = ['sfc', '--version']
    fake_process.register(version_command, stdout='1.2.3')

    linker = Linker(compiler=stub_fortran_compiler)
    linker.add_lib_flags('mylib', ['-L/my/lib', '-lmylib'])

    tool_box = ToolBox()
    tool_box.add_tool(stub_fortran_compiler)
    tool_box.add_tool(linker)

    config = BuildConfig('link_test', tool_box, fab_workspace=Path('/fab'),
                         mpi=False, openmp=False, multiprocessing=False)

    with raises(ValueError) as err:
        link_exe(config, libs=['mylib'], flags=['-fooflag', '-barflag'])
    assert "No target objects defined, linking aborted" in str(err.value)

    assert call_list(fake_process) == [version_command]

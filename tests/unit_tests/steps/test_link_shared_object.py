# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Tests linking a shared library.
"""
from pytest import warns
from pytest_subprocess.fake_process import FakeProcess

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.link import link_shared_object
from fab.tools.compiler import FortranCompiler
from fab.tools.linker import Linker

from tests.conftest import call_list


def test_run(stub_configuration: BuildConfig,
             stub_fortran_compiler: FortranCompiler,
             fake_process: FakeProcess) -> None:
    """
    Tests the construction of the command.
    """
    version_command = ['sfc', '-L/foo1/lib', '-L/foo2/lib', '--version']
    fake_process.register(version_command, stdout='1.2.3')
    link_command = ['sfc', 'bar.o', 'foo.o',
                    '-fooflag', '-barflag', '-fPIC', '-shared',
                    '-o', '/tmp/lib_my.so']
    fake_process.register(link_command, stdout='abc\ndef')

    stub_configuration.artefact_store[ArtefactSet.OBJECT_FILES] = {
        None: {'foo.o', 'bar.o'}
    }

    linker = Linker(compiler=stub_fortran_compiler)
    with warns(UserWarning,
               match="Replacing existing tool 'Linker - sln: scc' "
                     "with 'Linker - linker-some Fortran compiler: sfc'."):
        stub_configuration.tool_box.add_tool(linker)

    with warns(UserWarning, match="_metric_send_conn not set, "
                                  "cannot send metrics"):
        link_shared_object(stub_configuration, "/tmp/lib_my.so",
                           flags=['-fooflag', '-barflag'])
    assert call_list(fake_process) == [link_command]

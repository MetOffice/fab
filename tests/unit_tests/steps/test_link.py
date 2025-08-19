# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Exercises executable linkage step.
"""
from pathlib import Path

from pytest import warns
from pytest_subprocess.fake_process import FakeProcess

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.link import link_exe
from fab.tools.linker import Linker
from fab.tools.tool_box import ToolBox

from tests.conftest import call_list


class TestLinkExe:
    """
    Tests linking an executable.
    """
    def test_run(self, fake_process: FakeProcess,
                 stub_fortran_compiler) -> None:
        """
        Tests correct formation of command.
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

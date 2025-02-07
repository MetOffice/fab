# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''This module tests the linking step.
'''

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fab.artefacts import ArtefactSet, ArtefactStore
from fab.steps.link import link_exe
from fab.tools import FortranCompiler, Linker, ToolBox

import pytest


class TestLinkExe:
    '''Test class for linking an executable.
    '''
    def test_run(self, tool_box: ToolBox, mock_fortran_compiler):
        '''Ensure the command is formed correctly, with the flags at the
        end and that environment variable FFLAGS is picked up.
        '''
        config = SimpleNamespace(
            project_workspace=Path('workspace'),
            artefact_store=ArtefactStore(),
            tool_box=tool_box,
            mpi=False,
            openmp=False,
        )
        config.artefact_store[ArtefactSet.OBJECT_FILES] = \
            {'foo': {'foo.o', 'bar.o'}}

        with mock.patch.dict("os.environ",
                             {"FFLAGS": "-L/foo1/lib -L/foo2/lib"}):
            # We need to create the compiler here in order to pick
            # up the environment
            mock_compiler = FortranCompiler("mock_fortran_compiler",
                                            "mock_fortran_compiler.exe",
                                            "suite", module_folder_flag="",
                                            version_regex="something",
                                            syntax_only_flag=None,
                                            compile_flag=None,
                                            output_flag=None, openmp_flag=None)

            linker = Linker(compiler=mock_compiler)
            # Mark the linker as available to it can be added to the tool box
            linker._is_available = True

            # Add a custom library to the linker
            linker.add_lib_flags('mylib', ['-L/my/lib', '-lmylib'])
            tool_box.add_tool(linker, silent_replace=True)
            mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
            with mock.patch('fab.tools.tool.subprocess.run',
                            return_value=mock_result) as tool_run, \
                    pytest.warns(UserWarning,
                                 match="_metric_send_conn not "
                                       "set, cannot send metrics"):
                link_exe(config, libs=['mylib'],
                         flags=['-fooflag', '-barflag'])

        tool_run.assert_called_with(
            ['mock_fortran_compiler.exe', '-L/foo1/lib', '-L/foo2/lib',
             'bar.o', 'foo.o',
             '-L/my/lib', '-lmylib', '-fooflag', '-barflag',
             '-o', 'workspace/foo'],
            capture_output=True, env=None, cwd=None, check=False)

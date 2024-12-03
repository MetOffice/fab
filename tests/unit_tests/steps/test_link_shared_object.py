# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''Tests linking a shared library.
'''

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fab.artefacts import ArtefactSet, ArtefactStore
from fab.steps.link import link_shared_object
from fab.tools import FortranCompiler, Linker

import pytest


def test_run(tool_box):
    '''Ensure the command is formed correctly, with the flags at the
    end since they are typically libraries.'''

    config = SimpleNamespace(
        project_workspace=Path('workspace'),
        build_output=Path("workspace"),
        artefact_store=ArtefactStore(),
        openmp=False,
        tool_box=tool_box
    )
    config.artefact_store[ArtefactSet.OBJECT_FILES] = \
        {None: {'foo.o', 'bar.o'}}

    with mock.patch.dict("os.environ", {"FFLAGS": "-L/foo1/lib -L/foo2/lib"}):
        # We need to create the compiler here in order to pick
        # up the environment
        mock_compiler = FortranCompiler("mock_fortran_compiler",
                                        "mock_fortran_compiler.exe",
                                        "suite", module_folder_flag="",
                                        version_regex="something",
                                        syntax_only_flag=None,
                                        compile_flag=None, output_flag=None,
                                        openmp_flag=None)
        mock_compiler.run = mock.Mock()
        linker = Linker(mock_compiler)
        # Mark the linker as available so it can added to the tool box:
        linker._is_available = True
        tool_box.add_tool(linker, silent_replace=True)
        mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run, \
                pytest.warns(UserWarning, match="_metric_send_conn not set, "
                                                "cannot send metrics"):
            link_shared_object(config, "/tmp/lib_my.so",
                               flags=['-fooflag', '-barflag'])

    tool_run.assert_called_with(
        ['mock_fortran_compiler.exe', '-L/foo1/lib', '-L/foo2/lib', 'bar.o',
         'foo.o', '-fooflag', '-barflag', '-fPIC', '-shared',
         '-o', '/tmp/lib_my.so'],
        capture_output=True, env=None, cwd=None, check=False)

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

from fab.constants import OBJECT_FILES
from fab.steps.link import link_shared_object
from fab.tools import Linker

import pytest


def test_run(tool_box):
    '''Ensure the command is formed correctly, with the flags at the
    end since they are typically libraries.'''

    config = SimpleNamespace(
        project_workspace=Path('workspace'),
        build_output=Path("workspace"),
        artefact_store={OBJECT_FILES: {None: {'foo.o', 'bar.o'}}},
        tool_box=tool_box
    )

    with mock.patch('os.getenv', return_value='-L/foo1/lib -L/foo2/lib'):
        # We need to create a linker here to pick up the env var:
        linker = Linker("mock_link", "mock_link.exe", "vendor")
        # Mark the linker as available so it can added to the tool box:
        linker.is_available = True
        tool_box.add_tool(linker)
        mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run, \
                pytest.warns(UserWarning, match="_metric_send_conn not set, "
                                                "cannot send metrics"):
            link_shared_object(config, "/tmp/lib_my.so",
                               flags=['-fooflag', '-barflag'])

    tool_run.assert_called_with(
        ['mock_link.exe', '-L/foo1/lib', '-L/foo2/lib', 'bar.o', 'foo.o',
         '-fooflag', '-barflag', '-fPIC', '-shared', '-o', '/tmp/lib_my.so'],
        capture_output=True, env=None, cwd=None, check=False)

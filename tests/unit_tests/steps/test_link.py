# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fab.constants import OBJECT_FILES
from fab.steps.link import link_exe
from fab.newtools import Linker

import pytest


class TestLinkExe():
    def test_run(self, tool_box):
        # ensure the command is formed correctly, with the flags at the end (why?!)

        config = SimpleNamespace(
            project_workspace=Path('workspace'),
            artefact_store={OBJECT_FILES: {'foo': {'foo.o', 'bar.o'}}},
            tool_box=tool_box
        )

        with mock.patch('os.getenv', return_value='-L/foo1/lib -L/foo2/lib'):
            # We need to create a linker here to pick up the env var:
            linker = Linker("mock_link", "mock_link.exe", "mock-vendor")
            # Mark the linker as available to it can be added to the tool box
            linker.is_available = True
            tool_box.add_tool(linker)
            with mock.patch.object(linker, "run") as mock_run, \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                link_exe(config, flags=['-fooflag', '-barflag'])

        mock_run.assert_called_with([
            *sorted(['foo.o', 'bar.o']),
            '-fooflag', '-barflag',
            '-L/foo1/lib', '-L/foo2/lib',
            '-o', 'workspace/foo',
        ])

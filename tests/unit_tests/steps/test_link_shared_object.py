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
from fab.newtools import Linker

import pytest


def test_run(tool_box):
    '''Ensure the command is formed correctly, with the flags at the
    end since they are typically libraries.'''

    config = SimpleNamespace(
        project_workspace=Path('workspace'),
        build_output=Path("workspace"),
        _artefact_store={OBJECT_FILES: {None: {'foo.o', 'bar.o'}}},
        tool_box=tool_box
    )

    with mock.patch('os.getenv', return_value='-L/foo1/lib -L/foo2/lib'):
        # We need to create a linker here to pick up the env var:
        linker = Linker("mock_link", "mock_link.exe", "vendor")
        tool_box.add_tool(linker)
        with mock.patch.object(linker, "run") as mock_run, \
             pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            link_shared_object(config, "/tmp/lib_my.so", flags=['-fooflag', '-barflag'])

    mock_run.assert_called_with([
        *sorted(['foo.o', 'bar.o']),
        '-fooflag', '-barflag', '-fPIC', '-shared',
        '-L/foo1/lib', '-L/foo2/lib',
        '-o', '/tmp/lib_my.so',
    ])

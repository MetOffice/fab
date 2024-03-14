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

import pytest


class TestLinkExe(object):
    def test_run(self):
        # ensure the command is formed correctly, with the flags at the end (why?!)

        config = SimpleNamespace(
            project_workspace=Path('workspace'),
            artefact_store={OBJECT_FILES: {'foo': {'foo.o', 'bar.o'}}},
        )

        with mock.patch('os.getenv', return_value='-L/foo1/lib -L/foo2/lib'):
            with mock.patch('fab.steps.link.run_command') as mock_run, \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                link_exe(config, linker='foolink', flags=['-fooflag', '-barflag'])

        mock_run.assert_called_with([
            'foolink', '-o', 'workspace/foo',
            *sorted(['foo.o', 'bar.o']),
            '-L/foo1/lib', '-L/foo2/lib',
            '-fooflag', '-barflag',
        ])

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.folder import grab_folder
from fab.tools import ToolBox

import pytest


class TestGrabFolder():

    def test_trailing_slash(self):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            self._common(grab_src='/grab/source/', expect_grab_src='/grab/source/')

    def test_no_trailing_slash(self):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            self._common(grab_src='/grab/source', expect_grab_src='/grab/source/')

    def _common(self, grab_src, expect_grab_src):
        source_root = Path('/workspace/source')
        dst = 'bar'

        mock_config = SimpleNamespace(source_root=source_root,
                                      tool_box=ToolBox())
        with mock.patch('pathlib.Path.mkdir'):
            with mock.patch('fab.tools.tool.Tool.run') as mock_run:
                grab_folder(mock_config, src=grab_src, dst_label=dst)

        expect_dst = mock_config.source_root / dst
        mock_run.assert_called_once_with(
            additional_parameters=['--times', '--links', '--stats',
                                   '-ru', expect_grab_src, expect_dst])


class TestGrabFcm():

    def test_no_revision(self):
        source_root = Path('/workspace/source')
        source_url = '/www.example.com/bar'
        dst_label = 'bar'

        mock_config = SimpleNamespace(source_root=source_root,
                                      tool_box=ToolBox())
        with mock.patch('pathlib.Path.mkdir'):
            with mock.patch('fab.tools.tool.Tool.run') as mock_run, \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                fcm_export(config=mock_config, src=source_url, dst_label=dst_label)

        mock_run.assert_called_once_with(['export', '--force', source_url,
                                          str(source_root / dst_label)],
                                         env=None, cwd=None, capture_output=True)

    def test_revision(self):
        source_root = Path('/workspace/source')
        source_url = '/www.example.com/bar'
        dst_label = 'bar'
        revision = '42'

        mock_config = SimpleNamespace(source_root=source_root,
                                      tool_box=ToolBox())
        with mock.patch('pathlib.Path.mkdir'):
            with mock.patch('fab.tools.tool.Tool.run') as mock_run, \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                fcm_export(mock_config, src=source_url, dst_label=dst_label, revision=revision)

        mock_run.assert_called_once_with(
            ['export', '--force', '--revision', '42', f'{source_url}', str(source_root / dst_label)],
            env=None, cwd=None, capture_output=True)

    # todo: test missing repo
    # def test_missing(self):
    #     assert False

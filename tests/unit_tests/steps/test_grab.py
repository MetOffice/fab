##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Validate methods to obtain source.
"""
from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest import mark, warns
from pytest_subprocess.fake_process import FakeProcess

from fab.build_config import BuildConfig
from fab.steps.grab.fcm import fcm_export
from fab.steps.grab.folder import grab_folder
from fab.tools.tool_box import ToolBox


class TestGrabFolder:
    """
    Tests file directory grabbing.
    """
    @mark.parametrize(
        ['source', 'expected'],
        [
            ['/grab/source/', '/grab/source/'],
            ['/grab/source', '/grab/source/']
        ]
    )
    def test_source_path(self, source, expected,
                         fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests file directory grabbery.
        """
        version_command = ['rsync', '--version']
        fake_process.register(version_command, stdout='1.2.3')
        grab_command = ['rsync', '--times', '--links', '--stats',
                        '-ru', expected, '/fab/project/source/bar']
        fake_process.register(grab_command)

        config = BuildConfig('project', ToolBox(),
                             mpi=False, openmp=False, multiprocessing=False,
                             fab_workspace=Path('/fab'))

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            grab_folder(config, src=source, dst_label='bar')
        assert fake_process.call_count(grab_command) == 1


class TestGrabFcm:
    """
    Tests grabbing from FCM.
    """
    def test_no_revision(self, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests no revision, "head of branch" grab.
        """
        help_command = ['fcm', 'help']
        fake_process.register(help_command)
        grab_command = ['fcm', 'export', '--force', '/www.example.com/bar',
                        '/fab/project/source/bar']
        fake_process.register(grab_command)

        config = BuildConfig('project', ToolBox(),
                             mpi=False, openmp=False, multiprocessing=False,
                             fab_workspace=Path('/fab'))

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            fcm_export(config=config,
                       src='/www.example.com/bar',
                       dst_label='bar')
        assert fake_process.call_count(grab_command) == 1

    def test_revision(self, fs: FakeFilesystem, fake_process: FakeProcess) -> None:
        """
        Tests grabbing a specific revision.
        """
        help_command = ['fcm', 'help']
        fake_process.register(help_command)
        grab_command = ['fcm', 'export', '--force', '--revision', '42',
                        'http://www.example.com/bar',
                        '/fab/project/source/bar']
        fake_process.register(grab_command)

        config = BuildConfig('project', ToolBox(),
                             mpi=False, openmp=False, multiprocessing=False,
                             fab_workspace=Path('/fab'))

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            fcm_export(config, src='http://www.example.com/bar',
                       dst_label='bar', revision=42)
        assert fake_process.call_count(grab_command) == 1

    # todo: test missing repo
    # def test_missing(self):
    #     assert False

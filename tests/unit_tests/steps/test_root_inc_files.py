from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import BuildConfig
from fab.steps.root_inc_files import root_inc_files


class TestRootIncFiles(object):

    def test_vanilla(self):
        # ensure it copies the inc file
        inc_files = [Path('/foo/source/bar.inc')]

        config = BuildConfig('proj')
        config.artefact_store['all_source'] = inc_files

        with mock.patch('fab.steps.root_inc_files.shutil') as mock_shutil:
            with mock.patch('fab.steps.root_inc_files.Path.mkdir'), \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                root_inc_files(config)

        mock_shutil.copy.assert_called_once_with(inc_files[0], config.build_output)

    def test_skip_output_folder(self):
        # ensure it doesn't try to copy a file in the build output
        config = BuildConfig('proj')
        inc_files = [Path('/foo/source/bar.inc'), config.build_output / 'fab.inc']
        config.artefact_store['all_source'] = inc_files

        with mock.patch('fab.steps.root_inc_files.shutil') as mock_shutil:
            with mock.patch('fab.steps.root_inc_files.Path.mkdir'), \
                 pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                root_inc_files(config)

        mock_shutil.copy.assert_called_once_with(inc_files[0], config.build_output)

    def test_name_clash(self):
        # ensure raises an exception if there is a name clash
        inc_files = [Path('/foo/source/bar.inc'), Path('/foo/sauce/bar.inc')]

        config = BuildConfig('proj')
        config.artefact_store['all_source'] = inc_files

        with pytest.raises(FileExistsError):
            with mock.patch('fab.steps.root_inc_files.shutil'):
                with mock.patch('fab.steps.root_inc_files.Path.mkdir'), \
                     pytest.warns(DeprecationWarning,
                                  match="RootIncFiles is deprecated as .inc files are due to be removed."):
                    root_inc_files(config)

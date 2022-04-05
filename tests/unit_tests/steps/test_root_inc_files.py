from pathlib import Path
from unittest import mock

import pytest

from fab.constants import BUILD_OUTPUT
from fab.steps.root_inc_files import RootIncFiles


@pytest.fixture
def common_data():
    source_root = Path('/foo/source')
    build_output = source_root.parent / BUILD_OUTPUT
    return source_root, build_output


class TestRootIncFiles(object):

    def test_vanilla(self, common_data):
        # ensure it copies the inc file
        source_root, build_output, step = common_data
        inc_files = [Path('/foo/source/bar.inc')]
        step = RootIncFiles(source_root=source_root)

        with mock.patch('fab.steps.root_inc_files.shutil') as mock_shutil:
            step.run(artefact_store={'all_source': inc_files}, config=None)

        mock_shutil.copy.assert_called_once_with(inc_files[0], source_root.parent / BUILD_OUTPUT)

    def test_skip_output_folder(self, common_data):
        # ensure it doesn't try to copy a file in the build output
        source_root, build_output, step = common_data
        inc_files = [Path('/foo/source/bar.inc'), build_output / 'fab.inc']
        step = RootIncFiles(source_root=source_root)

        with mock.patch('fab.steps.root_inc_files.shutil') as mock_shutil:
            step.run(artefact_store={'all_source': inc_files}, config=None)

        mock_shutil.copy.assert_called_once_with(inc_files[0], build_output)

    def test_name_clash(self, common_data):
        # ensure raises an exception if there is a name clash
        source_root, build_output, step = common_data
        inc_files = [Path('/foo/source/bar.inc'), Path('/foo/sauce/bar.inc')]
        step = RootIncFiles(source_root=source_root)

        with pytest.raises(FileExistsError):
            with mock.patch('fab.steps.root_inc_files.shutil'):
                step.run(artefact_store={'all_source': inc_files}, config=None)

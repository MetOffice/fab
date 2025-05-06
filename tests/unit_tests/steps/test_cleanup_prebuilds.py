# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from datetime import timedelta, datetime
from pathlib import Path

from pytest import raises, warns

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.cleanup_prebuilds import (by_age, by_version_age,
                                         cleanup_prebuilds, remove_all_unused)
from fab.tools.tool_box import ToolBox
from fab.util import get_prebuild_file_groups


class TestCleanupPrebuilds(object):
    """
    Tests the prebuild cleaning step.
    """
    def test_init_no_args(self, tmp_path: Path) -> None:
        """
        Tests no arguments default to "all unused" functionality.
        """
        test_file = tmp_path / 'project/build_output/_prebuild/bar.o'
        test_file.parent.mkdir(parents=True)
        test_file.touch()
        unused_file = tmp_path / 'project/build_output/_prebuild/foo.o'
        unused_file.touch()

        configuration = BuildConfig('project', ToolBox(),
                                    fab_workspace=tmp_path)
        configuration.artefact_store[ArtefactSet.CURRENT_PREBUILDS] = [test_file]

        with warns(UserWarning,
                   match="_metric_send_conn not set, cannot send metrics"):
            cleanup_prebuilds(config=configuration)
        assert test_file.exists()
        assert not unused_file.exists()

    def test_init_bad_args(self):
        """
        Tests clean-up with random bad arguments.
        """
        with raises(ValueError):
            cleanup_prebuilds(config=None, all_unused=False)

    def test_by_age(self):
        """
        Tests expiration date helper function.
        """
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_age(older_than=timedelta(days=15),
                        prebuilds_ts=prebuilds_ts,
                        current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_age_current(self):
        """
        Tests expiration of up-to-date files.
        """
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_age(older_than=timedelta(days=15),
                        prebuilds_ts=prebuilds_ts,
                        current_files=prebuilds_ts.keys())
        assert result == set()

    def test_by_version_age(self):
        """
        Tests expiration of older versions of files.
        """
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_version_age(n_versions=1,
                                prebuilds_ts=prebuilds_ts,
                                current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_version_age_current(self):
        """
        Tests old version expiration when all files are current.
        """
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_version_age(n_versions=1,
                                prebuilds_ts=prebuilds_ts,
                                current_files=prebuilds_ts.keys())
        assert result == set()


def test_remove_all_unused(tmp_path: Path) -> None:
    """
    Tests removal of unused files.
    """
    starting_files = [
        tmp_path / 'michael.1943.o',
        tmp_path / 'eric.1943.o',
        tmp_path / 'terry.1942.o',
        tmp_path / 'graham.1941.o',
        tmp_path / 'john.1939.o',
    ]
    for fname in starting_files:
        fname.touch()

    current_files = [
        tmp_path / 'michael.1943.o',
        tmp_path / 'eric.1943.o'
    ]

    num_removed = remove_all_unused(starting_files, current_files)

    assert num_removed == 3

    assert sorted([fobject for fobject in tmp_path.iterdir()]) == sorted(current_files)


def test_get_prebuild_file_groups():
    """
    Tests grouping of filenames.
    """
    prebuild_files = [
        Path('foo.123.an'), Path('foo.234.an'), Path('foo.345.an'),
        Path('foo.123.o'), Path('foo.234.o'), Path('foo.345.o'),
        Path('foo.123.mod'), Path('foo.234.mod'), Path('foo.345.mod'),
    ]

    result = get_prebuild_file_groups(prebuild_files)

    assert result == {
        'foo.*.an': set(prebuild_files[0:3]),
        'foo.*.o': set(prebuild_files[3:6]),
        'foo.*.mod': set(prebuild_files[6:9]),
    }

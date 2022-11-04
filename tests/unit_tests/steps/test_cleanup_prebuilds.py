# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from datetime import timedelta, datetime
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
from fab.util import get_prebuild_file_groups

from fab.steps.cleanup_prebuilds import CleanupPrebuilds, remove_all_unused


class TestCleanupPrebuilds(object):

    def test_init_no_args(self):
        c = CleanupPrebuilds()
        assert not c.older_than
        assert not c.n_versions
        assert c.all_unused

    def test_init_bad_args(self):
        with pytest.raises(ValueError):
            CleanupPrebuilds(all_unused=False)

    def test_by_age(self):
        c = CleanupPrebuilds(older_than=timedelta(days=15))
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_age(prebuilds_ts=prebuilds_ts, current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_age_current(self):
        # same as test_by_age except all files are current so won't be deleted
        c = CleanupPrebuilds(older_than=timedelta(days=15))
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_age(prebuilds_ts=prebuilds_ts, current_files=prebuilds_ts.keys())
        assert result == set()

    def test_by_version_age(self):
        c = CleanupPrebuilds(n_versions=1)
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_version_age(prebuilds_ts, current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_version_age_current(self):
        # same as test_by_age except all files are current so won't be deleted
        c = CleanupPrebuilds(n_versions=1)
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_version_age(prebuilds_ts, current_files=prebuilds_ts.keys())
        assert result == set()


def test_remove_all_unused():

    found_files = [
        Path('michael.o'),
        Path('eric.o'),
        Path('terry.o'),
        Path('graham.o'),
        Path('john.o'),
    ]
    current_files = [
        Path('michael.o'),
        Path('eric.o'),
    ]

    # using autospec makes our mock receive the self param, which we want to check
    with mock.patch('pathlib.Path.unlink', autospec=True) as mock_unlink:
        num_removed = remove_all_unused(found_files, current_files)

    assert num_removed == 3
    mock_unlink.assert_has_calls([
        call(Path('terry.o')),
        call(Path('graham.o')),
        call(Path('john.o')),
    ])


def test_get_prebuild_file_groups():
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

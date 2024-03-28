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

from fab.constants import CURRENT_PREBUILDS
from fab.steps.cleanup_prebuilds import by_age, by_version_age, cleanup_prebuilds, remove_all_unused
from fab.util import get_prebuild_file_groups


class TestCleanupPrebuilds(object):

    def test_init_no_args(self):
        with mock.patch('fab.steps.cleanup_prebuilds.file_walk', return_value=[Path('foo.o')]), \
             pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            with mock.patch('fab.steps.cleanup_prebuilds.remove_all_unused') as mock_remove_all_unused:
                cleanup_prebuilds(config=mock.Mock(artefact_store={CURRENT_PREBUILDS: [Path('bar.o')]}))
        mock_remove_all_unused.assert_called_once_with(found_files=[Path('foo.o')], current_files=[Path('bar.o')])

    def test_init_bad_args(self):
        with pytest.raises(ValueError):
            cleanup_prebuilds(config=None, all_unused=False)

    def test_by_age(self):
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_age(older_than=timedelta(days=15), prebuilds_ts=prebuilds_ts, current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_age_current(self):
        # same as test_by_age except all files are current so won't be deleted
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_age(older_than=timedelta(days=15), prebuilds_ts=prebuilds_ts, current_files=prebuilds_ts.keys())
        assert result == set()

    def test_by_version_age(self):
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_version_age(n_versions=1, prebuilds_ts=prebuilds_ts, current_files=[])
        assert result == {Path('foo.234.o'), }

    def test_by_version_age_current(self):
        # same as test_by_age except all files are current so won't be deleted
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = by_version_age(n_versions=1, prebuilds_ts=prebuilds_ts, current_files=prebuilds_ts.keys())
        assert result == set()


def test_remove_all_unused():

    found_files = [
        Path('michael.1943.o'),
        Path('eric.1943.o'),
        Path('terry.1942.o'),
        Path('graham.1941.o'),
        Path('john.1939.o'),
    ]
    current_files = [
        Path('michael.1943.o'),
        Path('eric.1943.o'),
    ]

    # using autospec makes our mock recieve the self param, which we want to check
    with mock.patch('os.remove', autospec=True) as mock_remove:
        num_removed = remove_all_unused(found_files, current_files)

    assert num_removed == 3
    mock_remove.assert_has_calls([
        call(Path('terry.1942.o')),
        call(Path('graham.1941.o')),
        call(Path('john.1939.o')),
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

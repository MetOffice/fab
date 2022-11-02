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
            c = CleanupPrebuilds(all_unused=False)

    def test_by_age(self):
        c = CleanupPrebuilds(older_than=timedelta(days=15))
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_age(prebuilds_ts)
        assert result == {Path('foo.234.o'), }

    def test_by_version_age(self):
        c = CleanupPrebuilds(n_versions=1)
        prebuilds_ts = {
            Path('foo.123.o'): datetime(2022, 10, 31),
            Path('foo.234.o'): datetime(2022, 10, 1),
        }

        result = c.by_version_age(prebuilds_ts)
        assert result == {Path('foo.234.o'), }


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


def Test_get_prebuild_file_groups(object):
    prebuild_files = [Path()]
    result = get_prebuild_file_groups(prebuild_files)

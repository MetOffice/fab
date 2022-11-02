# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import pytest

from fab.steps.cleanup_prebuilds import CleanupPrebuilds


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
        pass

    def test_by_version_age(self):
        pass


def Test_remove_all_unused(object):
    pass

def Test_check_fs_access_time(object):
    pass

def Test_get_prebuild_file_groups(object):
    pass


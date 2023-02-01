# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.steps.grab.svn import _get_revision
import pytest


class Test_get_revision(object):
    # test the handling of the revision in the base class

    def test_no_revision(self):
        assert _get_revision(src='url') == ('url', None)

    def test_url_revision(self):
        assert _get_revision(src='url@rev') == ('url', 'rev')

    def test_revision_param(self):
        assert _get_revision(src='url', revision='rev') == ('url', 'rev')

    def test_both_matching(self):
        assert _get_revision(src='url@rev', revision='rev') == ('url', 'rev')

    def test_both_different(self):
        with pytest.raises(ValueError):
            assert _get_revision(src='url@rev', revision='bev')

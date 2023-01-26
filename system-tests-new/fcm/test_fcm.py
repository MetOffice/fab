# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil

import pytest


@pytest.fixture
def url(tmp_path):
    shutil.unpack_archive()
    return


class TestFcmExport(object):

    def test_vanilla(self, url):
        pass
        # Make sure we can export twice. Todo: we should probably clean existing files first?


class TestFcmCheckout(object):

    def test_clean(self):
        pass

    def test_new_folder(self):
        pass

    def test_working_copy(self):
        pass

    def test_not_working_copy(self):
        pass


class TestFcmMerge(object):

    def test_working_copy(self):
        pass

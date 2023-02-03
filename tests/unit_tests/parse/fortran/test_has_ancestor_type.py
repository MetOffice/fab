# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.parse.fortran_common import _has_ancestor_type


class Thing1(object):
    def __init__(self, parent):
        self.parent = parent


class Thing2(Thing1):
    pass


class Test_has_ancestor_type(object):

    def test_true(self):
        thing = Thing1(parent=Thing1(parent=Thing2(None)))
        assert _has_ancestor_type(thing, Thing2)

    def test_false(self):
        thing = Thing1(parent=Thing1(parent=Thing1(None)))
        assert not _has_ancestor_type(thing, Thing2)

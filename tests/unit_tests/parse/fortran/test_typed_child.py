
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from fab.parse.fortran_common import _typed_child


class Parent(object):
    def __init__(self, children=None):
        self.children = children


class Child1(Parent):
    pass


class Child2(Parent):
    pass


class Test_typed_child(object):

    def test_true(self):
        parent = Parent([Child1(), Child1(), Child2(), Child1()])
        assert _typed_child(parent, Child2)

    def test_false(self):
        parent = Parent([Child1(), Child1(), Child1(), Child1()])
        assert not _typed_child(parent, Child2)

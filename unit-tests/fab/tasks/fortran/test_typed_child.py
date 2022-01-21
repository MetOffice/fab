from fab.tasks.fortran import typed_child


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
        assert typed_child(parent, Child2)

    def test_false(self):
        parent = Parent([Child1(), Child1(), Child1(), Child1()])
        assert not typed_child(parent, Child2)

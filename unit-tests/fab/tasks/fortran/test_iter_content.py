from fab.tasks.fortran import _iter_content


class Node(object):
    def __init__(self, name, content=None):
        self.name = name
        self.content = content or []


class Test_iter_content(object):

    def test_vanilla(self):
        root = Node("root", [
            Node("child1"),
            Node("child2", [
                Node("grandchild1"),
                Node("grandchild2", [
                    Node("greatgrandchild1")
                ]),
            ]),
            Node("child3", [
                Node("grandchild3"),
            ]),

        ])

        result = [node.name for node in _iter_content(root)]
        assert result == ['root', 'child1', 'child2', 'grandchild1', 'grandchild2', 'greatgrandchild1', 'child3', 'grandchild3']

    def test_empty(self):
        assert [node.name for node in _iter_content(Node("foo"))] == ["foo"]

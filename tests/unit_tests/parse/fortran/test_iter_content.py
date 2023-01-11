from fab.parse.fortran import iter_content


class Node(object):
    def __init__(self, name, content=None):
        self.name = name
        if content is not None:
            self.content = content


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

        result = [node.name for node in iter_content(root)]
        assert result == ['root', 'child1', 'child2', 'grandchild1', 'grandchild2', 'greatgrandchild1', 'child3',
                          'grandchild3']

    def test_empty(self):
        assert [node.name for node in iter_content(Node("foo"))] == ["foo"]

    def test_deep(self):
        root = Node("root", content=[])
        cur = root
        for i in range(10):
            next_child = Node(str(i), content=[])
            cur.content.append(next_child)
            cur = next_child

        result = [node.name for node in iter_content(root)]
        assert result == ['root', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

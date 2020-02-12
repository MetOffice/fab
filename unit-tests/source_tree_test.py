##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path

from fab.database import StateDatabase
from fab.language import Analyser
from fab.source_tree import ExtensionVisitor, TreeDescent, TreeVisitor


class DummyVisitor(TreeVisitor):
    def __init__(self):
        self.visited = []

    def visit(self, candidate: Path):
        self.visited.append(candidate)


def test_descent(tmp_path: Path):
    tree_root = tmp_path / 'alpha'
    tree_root.mkdir()
    (tree_root / 'beta').mkdir()
    (tree_root / 'gamma').write_text('File in root')
    (tree_root / 'beta' / 'delta').write_text('File in beta')
    (tree_root / 'beta' / 'epsilon').write_text('Another file in beta')

    test_unit = TreeDescent(tree_root)
    visitor = DummyVisitor()
    test_unit.descend(visitor)

    assert visitor.visited == [tree_root / 'gamma',
                               tree_root / 'beta' / 'epsilon',
                               tree_root / 'beta' / 'delta']


class DummyAnalyser(Analyser):
    def __init__(self, db: StateDatabase):
        super().__init__(db)
        self.seen = []

    def analyse(self, filename: Path):
        self.seen.append(filename)


def test_extension_visitor(tmp_path: Path):
    db = StateDatabase(tmp_path)
    emap = {'.foo': DummyAnalyser(db),
            '.bar': DummyAnalyser(db)}
    test_unit = ExtensionVisitor(emap)
    test_unit.visit(tmp_path / 'file.foo')
    assert emap['.foo'].seen == [tmp_path / 'file.foo']
    assert emap['.bar'].seen == []

    test_unit.visit(tmp_path / 'dir' / 'file.bar')
    assert emap['.foo'].seen == [tmp_path / 'file.foo']
    assert emap['.bar'].seen == [tmp_path / 'dir' / 'file.bar']

    test_unit.visit(tmp_path / 'file.baz')
    assert emap['.foo'].seen == [tmp_path / 'file.foo']
    assert emap['.bar'].seen == [tmp_path / 'dir' / 'file.bar']

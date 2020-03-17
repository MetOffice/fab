##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Iterator, Union, List

from fab.database import SqliteStateDatabase, FileInfoDatabase, FileInfo
from fab.language import Analyser
from fab.reader import TextReader
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


class DummyReader(TextReader):
    @property
    def filename(self) -> Union[Path, str]:
        return Path('/dummy')

    def line_by_line(self) -> Iterator[str]:
        yield 'dummy'


class DummyAnalyserFoo(Analyser):
    last_seen: TextReader = DummyReader()

    def run(self):
        self.last_seen = self._reader
        return []


class DummyAnalyserBar(Analyser):
    last_seen: TextReader = DummyReader()

    def run(self):
        self.last_seen = self._reader
        return []


def test_extension_visitor(tmp_path: Path):
    foo_file = tmp_path / 'file.foo'
    foo_file.write_text('First file')
    (tmp_path / 'dir').mkdir()
    bar_file = tmp_path / 'dir' / 'file.bar'
    bar_file.write_text('Second file in subdirectory')

    db = SqliteStateDatabase(tmp_path)
    file_info = FileInfoDatabase(db)

    emap = {'.foo': DummyAnalyserFoo,
            '.bar': DummyAnalyserBar}
    test_unit = ExtensionVisitor(emap, db, tmp_path)

    test_unit.visit(foo_file)
    assert emap['.foo'].last_seen.filename == tmp_path / 'file.foo'
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert isinstance(emap['.bar'].last_seen, DummyReader)

    test_unit.visit(bar_file)
    assert emap['.foo'].last_seen.filename == tmp_path / 'file.foo'
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert emap['.bar'].last_seen.filename \
        == tmp_path / 'dir' / 'file.bar'
    assert file_info.get_file_info(bar_file) \
        == FileInfo(tmp_path / 'dir' / 'file.bar', 2333477459)

    test_unit.visit(tmp_path / 'file.baz')
    assert emap['.foo'].last_seen.filename == tmp_path / 'file.foo'
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert emap['.bar'].last_seen.filename \
        == tmp_path / 'dir' / 'file.bar'
    assert file_info.get_file_info(bar_file) \
        == FileInfo(tmp_path / 'dir' / 'file.bar', 2333477459)

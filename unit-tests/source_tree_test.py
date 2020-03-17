##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Iterator, Union, List, Mapping, Dict, Union, Type

from fab.database import SqliteStateDatabase, FileInfoDatabase, FileInfo
from fab.language import Analyser, Command, Task
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


tracker: Mapping[str, List[Path]] = {
    "analyser": [],
    "command": [],
}


def clear_tracker():
    tracker["analyser"] = []
    tracker["command"] = []


class DummyAnalyser(Analyser):
    def run(self):
        tracker["analyser"].append(self._reader)
        return []


class DummyCommand(Command):
    @property
    def as_list(self) -> List[str]:
        tracker["command"].append(self._filename)
        # Note that this is the command "true" which does nothing
        # (we're not trying to test the result of the command here)
        return ["true"]

    @property
    def output_filename(self) -> Path:
        return self._filename.with_suffix(".qux")


def test_extension_visitor(tmp_path: Path):
    foo_file = tmp_path / 'file.foo'
    foo_file.write_text('First file')
    (tmp_path / 'dir').mkdir()
    bar_file = tmp_path / 'dir' / 'file.bar'
    bar_file.write_text('Second file in subdirectory')

    db = SqliteStateDatabase(tmp_path)
    file_info = FileInfoDatabase(db)
    clear_tracker()

    emap: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.foo': DummyAnalyser,
        '.bar': DummyCommand
        }
    test_unit = ExtensionVisitor(emap, db, tmp_path)
    test_unit.visit(tmp_path / 'file.foo')

    assert tracker["analyser"] == [tmp_path / 'file.foo']
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert tracker["command"] == []

    test_unit.visit(tmp_path / 'dir' / 'file.bar')
    assert tracker["analyser"] == [tmp_path / 'file.foo']
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert tracker["command"] == [tmp_path / 'dir' / 'file.bar']
    assert file_info.get_file_info(bar_file) \
        == FileInfo(tmp_path / 'dir' / 'file.bar', 2333477459)

    test_unit.visit(tmp_path / 'file.baz')
    assert tracker["analyser"] == [tmp_path / 'file.foo']
    assert file_info.get_file_info(foo_file) \
        == FileInfo(tmp_path / 'file.foo', 345244617)
    assert tracker["command"] == [tmp_path / 'dir' / 'file.bar']
    assert file_info.get_file_info(bar_file) \
        == FileInfo(tmp_path / 'dir' / 'file.bar', 2333477459)
 

def test_nested_extension_visitor(tmp_path: Path):
    db = StateDatabase(tmp_path)
    clear_tracker()
    emap: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.foo': DummyAnalyser,
        '.bar': DummyCommand,
        '.qux': DummyAnalyser
        }
    test_unit = ExtensionVisitor(emap, db, tmp_path)
    test_unit.visit(tmp_path / 'file.foo')

    assert tracker["analyser"] == [tmp_path / 'file.foo']
    assert tracker["command"] == []

    test_unit.visit(tmp_path / 'dir' / 'file.bar')
    assert tracker["analyser"] == [tmp_path / 'file.foo',
                                   tmp_path / 'dir' / 'file.qux']
    assert tracker["command"] == [tmp_path / 'dir' / 'file.bar']

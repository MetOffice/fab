##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Iterator, Union, List, Mapping, Dict, Type

from fab.database import SqliteStateDatabase, FileInfoDatabase, FileInfo
from fab.language import Analyser, Command, Task
from fab.reader import TextReader
from fab.source_tree import ExtensionVisitor, TreeDescent, TreeVisitor


class DummyVisitor(TreeVisitor):
    def __init__(self):
        self.visited = []

    def visit(self, candidate: Path) -> List[Path]:
        self.visited.append(candidate)
        return []


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
    'analyser': [],
    'command': [],
}


def setup_function():
    tracker['analyser'] = []
    tracker['command'] = []


class DummyAnalyser(Analyser):
    def run(self):
        tracker['analyser'].append(self._reader.filename)
        return []


class DummyCommand(Command):
    @property
    def as_list(self) -> List[str]:
        tracker['command'].append(self._filename)
        return ['cp', str(self._filename), str(self.output_filename)]

    @property
    def output_filename(self) -> Path:
        return self._filename.with_suffix('.baz')


def test_extension_visitor(tmp_path: Path):
    foo_file = tmp_path / 'file.foo'
    foo_file.write_text('First file')
    (tmp_path / 'dir').mkdir()
    bar_file = tmp_path / 'dir' / 'file.bar'
    bar_file.write_text('Second file in subdirectory')
    baz_file = tmp_path / 'file.baz'  # Doesn't exist

    db = SqliteStateDatabase(tmp_path)
    file_info = FileInfoDatabase(db)

    emap: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.foo': DummyAnalyser,
        '.bar': DummyCommand
        }
    test_unit = ExtensionVisitor(emap, {}, db, tmp_path)
    test_unit.visit(foo_file)

    assert tracker['analyser'] == [foo_file]
    assert file_info.get_file_info(foo_file) \
        == FileInfo(foo_file, 345244617)
    assert tracker['command'] == []

    test_unit.visit(bar_file)
    assert tracker['analyser'] == [foo_file]
    assert file_info.get_file_info(foo_file) \
        == FileInfo(foo_file, 345244617)
    assert tracker['command'] == [bar_file]
    assert file_info.get_file_info(bar_file) \
        == FileInfo(bar_file, 2333477459)

    # Baz doesn't exist, so we're expecting no change
    test_unit.visit(baz_file)
    assert tracker['analyser'] == [foo_file]
    assert file_info.get_file_info(foo_file) \
        == FileInfo(foo_file, 345244617)
    assert tracker['command'] == [bar_file]
    assert file_info.get_file_info(bar_file) \
        == FileInfo(bar_file, 2333477459)


def test_nested_visit(tmp_path: Path):
    tree_root = tmp_path / 'nested'
    tree_root.mkdir()
    foo_file = tree_root / 'file.foo'
    foo_file.write_text('First file')
    bar_file = tree_root / 'file.bar'
    bar_file.write_text('Second file')
    # This file doesn't exist - it will be created by the
    # command task when run on the "bar" file
    baz_file = tree_root / 'file.baz'

    db = SqliteStateDatabase(tmp_path)
    file_info = FileInfoDatabase(db)

    emap: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.foo': DummyAnalyser,
        '.bar': DummyCommand,
        '.baz': DummyAnalyser
        }
    visitor = ExtensionVisitor(emap, {}, db, tmp_path)
    test_unit = TreeDescent(tree_root)
    test_unit.descend(visitor)

    assert tracker['analyser'] == [foo_file, baz_file]
    assert file_info.get_file_info(foo_file) \
        == FileInfo(foo_file, 345244617)
    assert file_info.get_file_info(baz_file) \
        == FileInfo(baz_file, 411763741)
    assert tracker['command'] == [bar_file]
    assert file_info.get_file_info(bar_file) \
        == FileInfo(bar_file, 411763741)

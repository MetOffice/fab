##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import pytest
from typing import Union, List, Dict, Type

from fab.database import SqliteStateDatabase
from fab.language import Analyser, Command, SingleFileCommand, Task
from fab.source_tree import ExtensionVisitor, TreeDescent, TreeVisitor
from fab.queue import QueueManager


class TestExtensionVisitor(object):
    def test_analyser(self, tmp_path: Path):
        (tmp_path / 'test.foo').write_text("First file")
        (tmp_path / 'directory').mkdir()
        (tmp_path / 'directory' / 'file.foo').write_text("Second file in directory")

        tracker: List[Path] = []

        class DummyTask(Analyser):
            def run(self):
                tracker.append(self._reader.filename)

        db = SqliteStateDatabase(tmp_path)
        emap: Dict[str, Union[Type[Task], Type[Command]]] = {
            '.foo': DummyTask
        }
        fmap: Dict[Type[Command], List[str]] = {}
        queue = QueueManager(1)
        test_unit = ExtensionVisitor(emap, fmap, db, tmp_path, queue)
        tracker.clear()
        test_unit.visit(tmp_path / 'test.foo')
        assert tracker == [tmp_path / 'test.foo']

        test_unit.visit(tmp_path / 'directory' / 'file.foo')
        assert tracker == [tmp_path / 'test.foo',
                           tmp_path / 'directory' / 'file.foo']

    def test_command(self, tmp_path: Path):
        (tmp_path / 'test.bar').write_text("File the first")
        (tmp_path / 'directory').mkdir()
        (tmp_path / 'directory' / 'test.bar').write_text("File the second in directory")

        tracker: List[Path] = []

        class DummyCommand(SingleFileCommand):
            @property
            def output(self) -> List[Path]:
                return [Path(tmp_path / 'wiggins')]

            @property
            def as_list(self) -> List[str]:
                tracker.append(self._filename)
                return ['cp', str(self._filename), str(self.output[0])]

        db = SqliteStateDatabase(tmp_path)
        emap: Dict[str, Union[Type[Task], Type[Command]]] = {
            '.bar': DummyCommand
        }
        fmap: Dict[Type[Command], List[str]] = {}
        queue = QueueManager(1)
        test_unit = ExtensionVisitor(emap, fmap, db, tmp_path, queue)
        tracker.clear()
        test_unit.visit(tmp_path / 'test.bar')
        assert tracker == [tmp_path / 'test.bar']

        test_unit.visit(tmp_path / 'directory' / 'test.bar')
        assert tracker == [tmp_path / 'test.bar',
                           tmp_path / 'directory/test.bar']

    def test_unrecognised_extension(self, tmp_path: Path):
        (tmp_path / 'test.what').write_text('Some test file')

        tracker: List[Path] = []

        class DummyAnalyser(Analyser):
            tracker: List[Path] = []

            def run(self):
                tracker.append(self._reader.filename)

        db = SqliteStateDatabase(tmp_path)
        emap: Dict[str, Union[Type[Task], Type[Command]]] = {
            '.expected': DummyAnalyser
        }
        fmap: Dict[Type[Command], List[str]] = {}
        queue = QueueManager(1)
        test_unit = ExtensionVisitor(emap, fmap, db, tmp_path, queue)
        tracker.clear()
        test_unit.visit(tmp_path / 'test.what')
        assert tracker == []

    def test_bad_extension_map(self, tmp_path: Path):
        (tmp_path / 'test.qux').write_text('Test file')

        class WhatnowCommand(Command):
            @property
            def as_list(self) -> List[str]:
                return []

            @property
            def output(self) -> List[Path]:
                return []

            @property
            def input(self) -> List[Path]:
                return []

        db = SqliteStateDatabase(tmp_path)
        emap: Dict[str, Union[Type[Task], Type[Command]]] = {
            '.qux': WhatnowCommand,
            }
        fmap: Dict[Type[Command], List[str]] = {}
        queue = QueueManager(1)
        test_unit = ExtensionVisitor(emap, fmap, db, tmp_path, queue)
        with pytest.raises(TypeError):
            test_unit.visit(tmp_path / 'test.qux')


class TestTreeDescent(object):
    @pytest.fixture(scope='class',
                    params=[None, 'nest'])
    def root_dir(self, request):
        yield request.param

    class DummyVisitor(TreeVisitor):
        def __init__(self, outfile: Path):
            self._outfile = outfile
            self.visited: List[Path] = []

        def visit(self, candidate: Path) -> List[Path]:
            self.visited.append(candidate)
            return []

        @property
        def output(self) -> List[Path]:
            return [self._outfile]

    def test_descent(self, tmp_path: Path, root_dir):
        if root_dir is not None:
            tree_root = tmp_path / root_dir
            tree_root.mkdir()
        else:
            tree_root = tmp_path
        (tree_root / 'alpha').write_text('File in root')
        (tree_root / 'beta').mkdir()
        (tree_root / 'beta' / 'gamma').write_text('File in beta')
        (tree_root / 'beta' / 'delta').write_text('Another file in beta')

        test_unit = TreeDescent(tree_root)
        visitor = self.DummyVisitor(tmp_path / 'foo')
        test_unit.descend(visitor)

        assert visitor.visited == [tree_root / 'beta' / 'gamma',
                                   tree_root / 'beta' / 'delta',
                                   tree_root / 'alpha']

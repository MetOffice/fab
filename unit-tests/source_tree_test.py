##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import pytest  # type: ignore
from typing import Union, List, Dict, Type, Tuple

from fab.database import SqliteStateDatabase
from fab.tasks import Analyser, Command, SingleFileCommand, Task
from fab.source_tree import SourceVisitor, TreeDescent, TreeVisitor


class TestSourceVisitor(object):
    def test_analyser(self, tmp_path: Path):
        (tmp_path / 'test.foo').write_text("First file")
        (tmp_path / 'directory').mkdir()
        (tmp_path / 'directory' / 'file.foo')\
            .write_text("Second file in directory")

        tracker: List[Path] = []

        class DummyTask(Analyser):
            def run(self):
                tracker.append(self._reader.filename)

        db = SqliteStateDatabase(tmp_path)
        smap: List[Tuple[str, Union[Type[Task], Type[Command]]]] = [
            (r'.*\.foo', DummyTask),
        ]
        fmap: Dict[Type[Command], List[str]] = {}

        def taskrunner(task):
            task.run()

        test_unit = SourceVisitor(smap, fmap, db, tmp_path, taskrunner)
        tracker.clear()

        test_unit.visit(tmp_path / 'test.foo')
        assert tracker == [tmp_path / 'test.foo']

        test_unit.visit(tmp_path / 'directory' / 'file.foo')
        assert tracker == [tmp_path / 'test.foo',
                           tmp_path / 'directory' / 'file.foo']

    def test_command(self, tmp_path: Path):
        (tmp_path / 'test.bar').write_text("File the first")
        (tmp_path / 'directory').mkdir()
        (tmp_path / 'directory' / 'test.bar') \
            .write_text("File the second in directory")

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
        smap: List[Tuple[str, Union[Type[Task], Type[Command]]]] = [
            (r'.*\.bar', DummyCommand),
        ]
        fmap: Dict[Type[Command], List[str]] = {}

        def taskrunner(task):
            task.run()

        test_unit = SourceVisitor(smap, fmap, db, tmp_path, taskrunner)
        tracker.clear()

        test_unit.visit(tmp_path / 'test.bar')
        assert tracker == [tmp_path / 'test.bar']

        test_unit.visit(tmp_path / 'directory' / 'test.bar')
        assert tracker == [tmp_path / 'test.bar',
                           tmp_path / 'directory/test.bar']

    def test_unrecognised_pattern(self, tmp_path: Path):
        (tmp_path / 'test.what').write_text('Some test file')

        tracker: List[Path] = []

        class DummyAnalyser(Analyser):
            def run(self):
                tracker.append(self._reader.filename)

        db = SqliteStateDatabase(tmp_path)
        smap: List[Tuple[str, Union[Type[Task], Type[Command]]]] = [
            (r'.*\.expected', DummyAnalyser),
        ]
        fmap: Dict[Type[Command], List[str]] = {}

        def taskrunner(task):
            task.run()

        test_unit = SourceVisitor(smap, fmap, db, tmp_path, taskrunner)
        tracker.clear()

        test_unit.visit(tmp_path / 'test.what')
        assert tracker == []

    def test_bad_source_map(self, tmp_path: Path):
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
        smap: List[Tuple[str, Union[Type[Task], Type[Command]]]] = [
            (r'.*\.qux', WhatnowCommand),
        ]
        fmap: Dict[Type[Command], List[str]] = {}

        def taskrunner(task):
            task.run()

        test_unit = SourceVisitor(smap, fmap, db, tmp_path, taskrunner)
        with pytest.raises(TypeError):
            test_unit.visit(tmp_path / 'test.qux')

    def test_repeated_extension(self, tmp_path: Path):
        (tmp_path / 'test.foo').write_text("First file")
        (tmp_path / 'directory').mkdir()
        (tmp_path / 'directory' / 'file.foo')\
            .write_text("Second file in directory")

        trackerA: List[Path] = []

        class DummyTaskA(Analyser):
            def run(self):
                trackerA.append(self._reader.filename)

        trackerB: List[Path] = []

        class DummyTaskB(Analyser):
            def run(self):
                trackerB.append(self._reader.filename)

        db = SqliteStateDatabase(tmp_path)
        smap: List[Tuple[str, Union[Type[Task], Type[Command]]]] = [
            (r'.*\.foo', DummyTaskA),
            (r'.*/directory/.*\.foo', DummyTaskB)
        ]
        fmap: Dict[Type[Command], List[str]] = {}

        def taskrunner(task):
            task.run()

        test_unit = SourceVisitor(smap, fmap, db, tmp_path, taskrunner)
        trackerA.clear()
        trackerB.clear()

        test_unit.visit(tmp_path / 'test.foo')
        assert trackerA == [tmp_path / 'test.foo']
        assert trackerB == []

        test_unit.visit(tmp_path / 'directory' / 'file.foo')
        assert trackerA == [tmp_path / 'test.foo']
        assert trackerB == [tmp_path / 'directory' / 'file.foo']


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

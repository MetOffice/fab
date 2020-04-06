# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
from pathlib import Path
from typing import Union, Sequence, Dict, List

from fab.database import DatabaseRows, StateDatabase
from fab.language import Analyser, Command, CommandTask, SingleFileCommand
from fab.reader import FileTextReader, StringTextReader


class DummyDatabase(StateDatabase):
    def execute(self,
                query: Union[Sequence[str], str],
                inserts: Dict[str, str]) -> DatabaseRows:
        pass


class AnalyserHarness(Analyser):
    def run(self) -> None:
        pass


class TestAnalyser(object):
    def test_constructor_with_file(self, tmp_path: Path):
        (tmp_path / 'foo').write_text('Hello')
        db = DummyDatabase()
        test_unit = AnalyserHarness(FileTextReader(tmp_path / 'foo'), db)
        assert test_unit.database == db
        assert test_unit.prerequisites == [tmp_path / 'foo']
        assert test_unit.products == []

    def test_constructor_with_string(self):
        db = DummyDatabase()
        test_unit = AnalyserHarness(StringTextReader('Hello'), db)
        assert test_unit.database == db
        assert test_unit.prerequisites == []
        assert test_unit.products == []


class SingleFileCommandHarness(SingleFileCommand):
    @property
    def as_list(self) -> List[str]:
        return []

    @property
    def output(self) -> List[Path]:
        return []


class TestSingleFileCommand(object):
    def test_constructor(self):
        test_unit = SingleFileCommandHarness(Path('this/that'),
                                             Path('thing/otherthing'),
                                             ['beef', 'cheese'])
        assert test_unit.input == [Path('this/that')]


class DummyCommand(Command):
    def __init__(self, workspace: Path, flags: List[str], stdout: bool):
        super().__init__(workspace, flags, stdout)
        self._output = workspace / 'run.touch'

    @property
    def as_list(self) -> List[str]:
        return ['touch', str(self._output)]

    @property
    def output(self) -> List[Path]:
        return [Path('output')]

    @property
    def input(self) -> List[Path]:
        return [Path('input')]


class DummyTerminalCommand(Command):
    def __init__(self, workspace: Path, flags: List[str], stdout: bool):
        super().__init__(workspace, flags, stdout)
        self._output = workspace / 'run.out'

    @property
    def as_list(self) -> List[str]:
        return ['echo', 'run']

    @property
    def output(self) -> List[Path]:
        return [self._output]

    @property
    def input(self) -> List[Path]:
        return [Path('input')]


class TestCommandTask(object):
    def test_constructor(self):
        test_unit = CommandTask(DummyCommand(Path('workspace'),
                                             ['wargle', 'bargle'],
                                             False))
        assert test_unit.prerequisites == [Path('input')]
        assert test_unit.products == [Path('output')]

    def test_run_file_output(self, tmp_path: Path):
        test_unit = CommandTask(DummyCommand(tmp_path,
                                             ['wargle', 'bargle'],
                                             False))
        test_unit.run()
        assert (tmp_path / 'run.touch').exists()

    def test_run_terminal_output(self, tmp_path: Path):
        test_unit = CommandTask(DummyTerminalCommand(tmp_path,
                                                     ['wargle', 'bargle'],
                                                     True))
        test_unit.run()
        assert (tmp_path / 'run.out').exists()
        assert (tmp_path / 'run.out').read_text() == 'run\n'

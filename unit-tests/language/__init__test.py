# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
from pathlib import Path
from typing import Iterator, Union, Sequence, Dict, List

from fab.database import StateDatabase, DatabaseRows
from fab.language import Analyser, Command, CommandTask, SingleFileCommand
from fab.reader import TextReader


class DummyReader(TextReader):
    @property
    def filename(self) -> Union[Path, str]:
        return '<dummy>'

    def line_by_line(self) -> Iterator[str]:
        pass


class DummyDatabase(StateDatabase):
    def execute(self,
                query: Union[Sequence[str], str],
                inserts: Dict[str, str]) -> DatabaseRows:
        pass


class AnalyserHarness(Analyser):
    def run(self) -> None:
        pass


class TestAnalyser(object):
    def test_constructor(self):
        db = DummyDatabase()
        test_unit = AnalyserHarness(DummyReader(), db)
        assert test_unit.database == db
        assert test_unit.prerequisites == ['<dummy>']
        assert test_unit.products == []


class SingleFileCommandHarness(SingleFileCommand):
    @property
    def as_list(self) -> List[str]:
        pass

    @property
    def output(self) -> List[Path]:
        pass


class TestSingleFileCommand(object):
    def test_constructor(self):
        test_unit = SingleFileCommandHarness(Path('this/that'),
                                             Path('thing/otherthing'),
                                             ['beef', 'cheese'])
        assert test_unit.input == [Path('this/that')]


class DummyCommand(Command):
    def __init__(self, workspace: Path, flags: Sequence[str], stdout: bool):
        super().__init__(workspace, flags, stdout)
        self._output = workspace / 'run.touch'

    @property
    def as_list(self) -> List[str]:
        return ['touch', self._output]

    @property
    def output(self) -> List[Path]:
        return [Path('output')]

    @property
    def input(self) -> List[Path]:
        return [Path('input')]


class DummyTerminalCommand(Command):
    def __init__(self, workspace: Path, flags: Sequence[str], stdout: bool):
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

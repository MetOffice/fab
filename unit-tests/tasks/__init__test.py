# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
from pathlib import Path
from typing import Union, Sequence, Dict, List

from fab.database import DatabaseRows, StateDatabase
from fab.tasks import Analyser, SingleFileCommand
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

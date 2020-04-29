##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from textwrap import dedent

from pytest import fail  # type: ignore

from fab.reader import FileTextReader, StringTextReader


class TestFileTextReader:
    def test_constructor(self, tmp_path: Path):
        test_file = tmp_path / 'teapot/cheese.boo'
        test_file.parent.mkdir()
        test_file.write_text('')
        test_unit = FileTextReader(test_file)
        assert test_unit.filename == test_file

    def test_reading(self, tmp_path: Path):
        test_file = tmp_path / 'beef.food'
        test_file.write_text('This is my test file\nIt has two lines')

        test_unit = FileTextReader(test_file)
        content = [line for line in test_unit.line_by_line()]
        assert content == ['This is my test file\n',
                           'It has two lines']

        # Call again on a now read file...
        for _ in test_unit.line_by_line():
            fail(' No lines should be generated from a read file')


class TestStringTextReader:
    def test_constructor(self):
        string = dedent('''
            I am in the infantry
            Battlemechs can stand on me.
            ''')
        test_unit = StringTextReader(string)
        assert isinstance(test_unit.filename, str)
        assert test_unit.filename.startswith('[string:')

    def test_reading(self, tmp_path: Path):
        test_file = tmp_path / 'beef.food'
        test_file.write_text('This is my test file\nIt has two lines')

        test_unit = FileTextReader(test_file)
        content = [line for line in test_unit.line_by_line()]
        assert content == ['This is my test file\n',
                           'It has two lines']

        # Call again on a now read file...
        for _ in test_unit.line_by_line():
            fail(' No lines should be generated from a read file')

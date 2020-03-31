##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import sqlite3
import pytest  # type: ignore

from fab.database import (DatabaseRows,
                          FileInfo,
                          FileInfoDatabase,
                          SqliteStateDatabase,
                          WorkingStateException)


class TestFileInfo(object):
    def test_constructor(self):
        test_unit = FileInfo(Path('stuff/nonsense'), 1234)
        assert test_unit.filename == Path('stuff/nonsense')
        assert test_unit.adler32 == 1234

    def test_equality(self):
        first = FileInfo(Path('stuff/nonsense'), 1234)
        with pytest.raises(ValueError):
            _ = first == 'Not a FileInfo'

        second = FileInfo(Path('stuff/nonsense'), 1234)
        assert first == second
        assert second == first

        second = FileInfo(Path('bobbins'), 4321)
        assert first != second
        assert second != first


class TestDatabaseRows(object):
    def test_iteration(self):
        connection = sqlite3.connect(':memory:')
        connection.execute('''create table test_table
                              (first integer, second character(10))''')
        connection.commit()

        cursor = connection.cursor()
        cursor.execute('select * from test_table')
        test_unit = DatabaseRows(cursor)
        assert list(iter(test_unit)) == []

        connection.execute('''insert into test_table (first, second)
                              values (13, "spooky")''')
        connection.commit()
        cursor = connection.cursor()
        cursor.execute('select * from test_table')
        test_unit = DatabaseRows(cursor)
        assert list(iter(test_unit)) == [(13, 'spooky')]

        connection.execute('''insert into test_table (first, second)
                              values (666, "devilish")''')
        connection.commit()
        cursor = connection.cursor()
        cursor.execute('select * from test_table')
        test_unit = DatabaseRows(cursor)
        assert list(iter(test_unit)) == [(13, 'spooky'),
                                         (666, 'devilish')]


class TestSQLiteStateDatabase(object):
    def test_constructor(self, tmp_path: Path):
        _ = SqliteStateDatabase(tmp_path)

        db_file = tmp_path / 'state.db'
        assert db_file.exists()

        # Check we can open the database without exceptions
        connection = sqlite3.Connection(str(db_file))
        connection.close()

        _ = SqliteStateDatabase(tmp_path / 'extra')

        db_file = tmp_path / 'extra' / 'state.db'
        assert db_file.exists()

        # Check it is a database file...
        connection = sqlite3.Connection(str(db_file))
        connection.close()


class TestFileInfoDatabase(object):
    def test_file_info(self, tmp_path: Path):
        test_unit = FileInfoDatabase(SqliteStateDatabase(tmp_path))

        with pytest.raises(WorkingStateException):
            test_unit.get_file_info(Path('foo.f90'))
        assert list(test_unit.get_all_filenames()) == []

        test_unit.add_file_info(Path('foo.f90'), 1234)
        assert list(test_unit.get_all_filenames()) == [Path('foo.f90')]
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 1234)

        test_unit.add_file_info(Path('bar/baz.f90'), 5786)
        assert list(test_unit.get_all_filenames()) == [Path('bar/baz.f90'),
                                                       Path('foo.f90')]
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 1234)
        assert test_unit.get_file_info(Path('bar/baz.f90')) \
            == FileInfo(Path('bar/baz.f90'), 5786)

        test_unit.add_file_info(Path('foo.f90'), 987)
        assert list(test_unit.get_all_filenames()) == [Path('bar/baz.f90'),
                                                       Path('foo.f90')]
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 987)
        assert test_unit.get_file_info(Path('bar/baz.f90')) \
            == FileInfo(Path('bar/baz.f90'), 5786)

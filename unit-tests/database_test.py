##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import sqlite3
import pytest  # type: ignore
from fab import FabException
from fab.database import (DatabaseRows,
                          FileInfo,
                          FileInfoDatabase,
                          SqliteStateDatabase)


class TestFileInfo(object):
    def test_constructor(self):
        test_unit = FileInfo(Path('stuff/nonsense'), 1234)
        assert test_unit.filename == Path('stuff/nonsense')
        assert test_unit.adler32 == 1234

    def equality_cases(self, request):
        yield request.param

    def test_equality(self):
        first = FileInfo(Path('stuff/nonsense'), 5678)
        with pytest.raises(ValueError):
            _ = first == 'Not a FileInfo'

        second = FileInfo(Path('stuff/nonsense'), 5678)
        assert first == second
        assert second == first

        second = FileInfo(Path('bobbins'), 5678)
        assert first != second

        second = FileInfo(Path('stuff/nonsense'), 1234)
        assert first != second

        second = FileInfo(Path('bobbins'), 1234)
        assert first != second


class TestDatabaseRows(object):
    def test_iteration(self):
        test_unit = DatabaseRows(None)
        with pytest.raises(StopIteration):
            next(test_unit)

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
    def test_creation(self, tmp_path: Path):
        database = SqliteStateDatabase(tmp_path)

        database.execute('''create table first_table
                            (anything integer)''', {})

        # Issuing a query should have created the database
        db_file = tmp_path / 'state.db'
        assert db_file.exists()

        # A second execute should work with no issue
        database.execute('''create table second_table
                            (anything integer)''', {})

        # Since the connection should persist, removing
        # the database at this point should cause an error
        # when another execute is raised
        db_file.unlink()
        with pytest.raises(sqlite3.OperationalError):
            database.execute('''create table third_table
                                (anything integer)''', {})

        # And it shouldn't have created the database again
        assert not db_file.exists()


class TestFileInfoDatabase(object):
    def test_iteration(self, tmp_path: Path):
        test_unit = FileInfoDatabase(SqliteStateDatabase(tmp_path))
        assert list(iter(test_unit)) == []

        test_unit.add_file_info(Path('foo.f90'), 1234)
        assert list(iter(test_unit)) == [FileInfo(Path('foo.f90'), 1234)]

        test_unit.add_file_info(Path('bar/baz.f90'), 5786)
        assert list(iter(test_unit)) == [FileInfo(Path('bar/baz.f90'), 5786),
                                         FileInfo(Path('foo.f90'), 1234)]

        # Add a new version of an existing file
        #
        test_unit.add_file_info(Path('foo.f90'), 987)
        assert list(iter(test_unit)) == [FileInfo(Path('bar/baz.f90'), 5786),
                                         FileInfo(Path('foo.f90'), 987)]

    def test_getter(self, tmp_path: Path):
        test_unit = FileInfoDatabase(SqliteStateDatabase(tmp_path))
        with pytest.raises(FabException):
            test_unit.get_file_info(Path('anything'))

        test_unit.add_file_info(Path('teapot.c'), 31337)
        assert test_unit.get_file_info(Path('teapot.c')) \
            == FileInfo(Path('teapot.c'), 31337)

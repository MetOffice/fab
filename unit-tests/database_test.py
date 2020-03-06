##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import sqlite3
import pytest  # type: ignore

from fab.database import SqliteStateDatabase, \
                         FileInfoDatabase, \
                         FileInfo, \
                         WorkingStateException


class TestSQLiteStateDatabase(object):
    def test_constructor(self, tmp_path: Path):
        _ = SqliteStateDatabase(tmp_path)

        db_file = tmp_path / 'state.db'
        assert db_file.exists()

        # Check we can open the database without exceptions
        connection = sqlite3.Connection(str(db_file))
        connection.close()


class TestFileInfoDatabase(object):
    def test_file_info(self, tmp_path: Path):
        test_unit = FileInfoDatabase(SqliteStateDatabase(tmp_path))

        with pytest.raises(WorkingStateException):
            test_unit.get_file_info(Path('foo.f90'))

        test_unit.add_file_info(Path('foo.f90'), 1234)
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 1234)

        test_unit.add_file_info(Path('bar/baz.f90'), 5786)
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 1234)
        assert test_unit.get_file_info(Path('bar/baz.f90')) \
            == FileInfo(Path('bar/baz.f90'), 5786)

        test_unit.add_file_info(Path('foo.f90'), 987)
        assert test_unit.get_file_info(Path('foo.f90')) \
            == FileInfo(Path('foo.f90'), 987)
        assert test_unit.get_file_info(Path('bar/baz.f90')) \
            == FileInfo(Path('bar/baz.f90'), 5786)

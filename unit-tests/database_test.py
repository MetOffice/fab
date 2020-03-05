##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import pytest  # type: ignore

from fab.database import StateDatabase, FileInfo, WorkingStateException


class TestStateDatabase(object):
    def test_file_info(self, tmp_path: Path):
        test_unit = StateDatabase(tmp_path)

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

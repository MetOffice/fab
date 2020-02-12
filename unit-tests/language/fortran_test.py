##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
from pathlib import Path
from typing import List, Sequence

import pytest

from fab.database import StateDatabase, WorkingStateException
from fab.language.fortran import FortranAnalyser, FortranWorkingState


class TestFortranWorkingSpace:
    def test_add(self, tmp_path):
        database = StateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        # Add a file containing a program unit
        #
        test_unit.add_fortran_program_unit('foo', tmp_path / 'foo.f90')
        assert test_unit.filenames_from_program_unit('foo') \
            == [tmp_path / 'foo.f90']
        with pytest.raises(WorkingStateException):
            _ = test_unit.filenames_from_program_unit('bar')
        assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
            == ['foo']
        with pytest.raises(WorkingStateException):
            _ = test_unit.program_units_from_file(tmp_path / 'bar.F90')

        # Add a second file containing a second program unit
        #
        test_unit.add_fortran_program_unit('bar', tmp_path / 'bar.F90')
        assert test_unit.filenames_from_program_unit('foo') \
            == [tmp_path / 'foo.f90']
        assert test_unit.filenames_from_program_unit('bar') \
            == [tmp_path / 'bar.F90']
        with pytest.raises(WorkingStateException):
            _ = test_unit.filenames_from_program_unit('baz')
        assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
            == ['foo']
        assert test_unit.program_units_from_file(tmp_path / 'bar.F90') \
            == ['bar']
        with pytest.raises(WorkingStateException):
            _ = test_unit.program_units_from_file(tmp_path / 'baz.F90')

        # Add a third file also containing a third program unit and another
        # copy of the first
        #
        test_unit.add_fortran_program_unit('baz', tmp_path / 'baz.f90')
        test_unit.add_fortran_program_unit('foo', tmp_path / 'baz.f90')
        assert test_unit.filenames_from_program_unit('foo') \
            == [tmp_path / 'foo.f90', tmp_path / 'baz.f90']
        assert test_unit.filenames_from_program_unit('bar') \
            == [tmp_path / 'bar.F90']
        assert test_unit.filenames_from_program_unit('baz') \
            == [tmp_path / 'baz.f90']
        with pytest.raises(WorkingStateException):
            _: Sequence[Path] = test_unit.filenames_from_program_unit('qux')
        assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
            == ['foo']
        assert test_unit.program_units_from_file(tmp_path / 'bar.F90') \
            == ['bar']
        assert test_unit.program_units_from_file(tmp_path / 'baz.f90') \
            == ['baz', 'foo']
        with pytest.raises(WorkingStateException):
            _ = test_unit.program_units_from_file(tmp_path / 'qux.F90')

        # Remove a previous added file
        test_unit.remove_fortran_file(tmp_path / 'baz.f90')
        assert test_unit.filenames_from_program_unit('foo') \
            == [tmp_path / 'foo.f90']
        assert test_unit.filenames_from_program_unit('bar') \
            == [tmp_path / 'bar.F90']
        with pytest.raises(WorkingStateException):
            _: Sequence[Path] = test_unit.filenames_from_program_unit('baz')
        assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
            == ['foo']
        assert test_unit.program_units_from_file(tmp_path / 'bar.F90') \
            == ['bar']
        with pytest.raises(WorkingStateException):
            _ = test_unit.program_units_from_file(tmp_path / 'baz.f90')

    def test_unit_iterator(self, tmp_path):
        database = StateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        test_unit.add_fortran_program_unit('foo', tmp_path / 'foo.f90')
        test_unit.add_fortran_program_unit('bar', tmp_path / 'bar.F90')
        test_unit.add_fortran_program_unit('baz', tmp_path / 'baz.f90')
        test_unit.add_fortran_program_unit('foo', tmp_path / 'baz.f90')

        expected = [('bar', [tmp_path / 'bar.F90']),
                    ('baz', [tmp_path / 'baz.f90']),
                    ('foo', [tmp_path / 'baz.f90', tmp_path / 'foo.f90'])]

        assert list(test_unit.iterate_program_units()) == expected


class TestFortranAnalyser(object):
    def test_analyser_program_units(self, caplog, tmp_path):
        caplog.set_level(logging.DEBUG)

        test_file: Path = tmp_path / 'test.f90'
        test_file.write_text('''
program foo

  implicit none

end program foo

module bar

  implicit none

end module bar

function baz(first, second)

  implicit none

end function baz

subroutine qux()

  implicit none

end subroutine qux
''')
        units: List[str] = ['foo', 'bar', 'baz', 'qux']

        database: StateDatabase = StateDatabase(tmp_path)
        test_unit = FortranAnalyser(database)
        test_unit.analyse(test_file)
        working_state = FortranWorkingState(database)
        assert working_state.program_units_from_file(test_file) == units
        for unit in units:
            assert working_state.filenames_from_program_unit(unit) \
                == [test_file]

    def test_analyser_scope(self, caplog, tmp_path):
        caplog.set_level(logging.DEBUG)

        test_file: Path = tmp_path / 'test.f90'
        test_file.write_text('''
program fred

  implicit none

  if (something) then
    named: do i=1, 10
    end do named
  endif

end program

module barney

  implicit none

  type betty_type
    integer :: property
  end type

  interface betty_type
    procedure betty_constructor
  end

end module
''')
        units: List[str] = ['fred', 'barney']

        database: StateDatabase = StateDatabase(tmp_path)
        test_unit = FortranAnalyser(database)
        test_unit.analyse(test_file)
        working_state = FortranWorkingState(database)
        assert working_state.program_units_from_file(test_file) == units
        for unit in units:
            assert working_state.filenames_from_program_unit(unit) \
                == [test_file]

    def test_harvested_data(self, caplog, tmp_path):
        caplog.set_level(logging.DEBUG)

        first_file: Path = tmp_path / 'other.F90'
        first_file.write_text('''
program betty
  use barney_mod, only :: dino
  implicit none
end program betty

module barney_mod
end module barney_mod
''')
        second_file: Path = tmp_path / 'test.f90'
        second_file.write_text('''
module barney_mod
end module barney_mod
''')

        database: StateDatabase = StateDatabase(tmp_path)
        test_unit = FortranAnalyser(database)
        test_unit.analyse(first_file)
        test_unit.analyse(second_file)

        fdb = FortranWorkingState(database)
        assert list(fdb.iterate_program_units()) \
            == [('barney_mod', [first_file, second_file]),
                ('betty', [first_file])]

        # Repeat the scan of second_file, there should be no change.
        #
        test_unit.analyse(second_file)

        fdb = FortranWorkingState(database)
        assert list(fdb.iterate_program_units()) \
            == [('barney_mod', [first_file, second_file]),
                ('betty', [first_file])]

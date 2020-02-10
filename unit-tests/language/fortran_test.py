##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
from pathlib import Path
from typing import List, Sequence

import pytest

from fab.database import WorkingStateException
from fab.language.fortran import FortranAnalyser, FortranWorkingState


def test_program_unit_per_file(tmp_path):
    test_unit = FortranWorkingState(tmp_path)

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

    # Add a third file also containing a third program unit and another copy
    # of the first
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


def test_analyser_program_units(caplog, tmp_path):
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

    database = FortranWorkingState(tmp_path)
    test_unit = FortranAnalyser(database)
    test_unit.analyse(test_file)
    assert database.program_units_from_file(test_file) == units
    for unit in units:
        assert database.filenames_from_program_unit(unit) == [test_file]


def test_analyser_scope(caplog, tmp_path):
    caplog.set_level(logging.DEBUG)

    test_file: Path = tmp_path / '.test.f90'
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

    database = FortranWorkingState(tmp_path)
    test_unit = FortranAnalyser(database)
    test_unit.analyse(test_file)
    assert database.program_units_from_file(test_file) == units
    for unit in units:
        assert database.filenames_from_program_unit(unit) == [test_file]

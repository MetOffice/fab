##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from typing import Sequence

import pytest

from fab.database import WorkingState, WorkingStateException


def test_program_unit_per_file(tmp_path):
    test_unit = WorkingState(tmp_path)

    # Add a file containing a program unit
    #
    test_unit.add_fortran_program_unit('foo', tmp_path/'foo.f90')
    assert test_unit.filenames_from_program_unit('foo') \
           == [tmp_path/'foo.f90']
    with pytest.raises(WorkingStateException):
        _ = test_unit.filenames_from_program_unit('bar')
    assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
           == ['foo']
    with pytest.raises(WorkingStateException):
        _ = test_unit.program_units_from_file(tmp_path / 'bar.F90')

    # Add a second file containing a second program unit
    #
    test_unit.add_fortran_program_unit('bar', tmp_path/'bar.F90')
    assert test_unit.filenames_from_program_unit('foo') \
           == [tmp_path/'foo.f90']
    assert test_unit.filenames_from_program_unit('bar') \
           == [tmp_path/'bar.F90']
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
    test_unit.add_fortran_program_unit('baz', tmp_path/'baz.f90')
    test_unit.add_fortran_program_unit('foo', tmp_path/'baz.f90')
    assert test_unit.filenames_from_program_unit('foo') \
           == [tmp_path/'foo.f90', tmp_path/'baz.f90']
    assert test_unit.filenames_from_program_unit('bar') \
           == [tmp_path/'bar.F90']
    assert test_unit.filenames_from_program_unit('baz') \
           == [tmp_path/'baz.f90']
    with pytest.raises(WorkingStateException):
        _: Sequence[Path] = test_unit.filenames_from_program_unit('qux')
    assert test_unit.program_units_from_file(tmp_path / 'foo.f90') \
           == ['foo']
    assert test_unit.program_units_from_file(tmp_path / 'bar.F90') \
           == ['bar']
    assert test_unit.program_units_from_file(tmp_path / 'baz.f90') \
           == ['baz', 'foo']
    with pytest.raises(WorkingStateException):
        _ = test_unit.program_units_from_file(tmp_path/'qux.F90')

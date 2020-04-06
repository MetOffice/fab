##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterator, List, Union, Sequence

import pytest  # type: ignore

from fab.database import SqliteStateDatabase, WorkingStateException
from fab.language import TaskException, CommandTask
from fab.language.fortran import (FortranAnalyser,
                                  FortranCompiler,
                                  FortranLinker,
                                  FortranNormaliser,
                                  FortranPreProcessor,
                                  FortranWorkingState)
from fab.reader import FileTextReader, StringTextReader, TextReader


class TestFortranWorkingSpace:
    @staticmethod
    def _check_ws(test_unit: FortranWorkingState,
                  expected_unit: Dict[str, Sequence[Path]],
                  expected_filename: Dict[Path, Sequence[str]],
                  expected_dependency: Dict[str, Sequence[str]]):
        for unit, unit_filename in expected_unit.items():
            if unit.startswith('!'):
                with pytest.raises(WorkingStateException):
                    _ = test_unit.filenames_from_program_unit(unit[1:])
            else:
                assert test_unit.filenames_from_program_unit(unit) \
                    == unit_filename

        for filename, filename_unit in expected_filename.items():
            if filename.suffix == '.not':
                with pytest.raises(WorkingStateException):
                    actual_filename: Path = filename.with_suffix('')
                    _ = test_unit.program_units_from_file(actual_filename)
            else:
                assert test_unit.program_units_from_file(filename) \
                    == filename_unit

        for unit, prerequisites in expected_dependency.items():
            assert test_unit.depends_on(unit) == prerequisites

    def test_add_remove_sequence(self, tmp_path):
        '''
        Walks a FortranWorkingState object through a sequence of adds and
        removes checking the contents at each stage.
        '''
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        # Add a file containing a program unit and an unsatisfied dependency.
        #
        expected_unit = {'foo': [tmp_path / 'foo.f90'],
                         '!bar': []}
        expected_filename = {tmp_path / 'foo.f90': ['foo'],
                             tmp_path / 'bar.F90.not': []}
        expected_dependency = {'foo': ['bar']}
        test_unit.add_fortran_program_unit('foo', tmp_path / 'foo.f90')
        test_unit.add_fortran_dependency('foo', 'bar')
        self._check_ws(test_unit,
                       expected_unit,
                       expected_filename,
                       expected_dependency)

        # Add a second file containing a second program unit.
        #
        # This satisfies the previously dangling dependency and adds a new
        # one.
        #
        expected_unit = {'foo': [tmp_path / 'foo.f90'],
                         'bar': [tmp_path / 'bar.F90'],
                         '!baz': []}
        expected_filename = {tmp_path / 'foo.f90': ['foo'],
                             tmp_path / 'bar.F90': ['bar'],
                             tmp_path / 'baz.F90.not': []}
        expected_dependency = {'foo': ['bar'],
                               'bar': ['baz']}
        test_unit.add_fortran_program_unit('bar', tmp_path / 'bar.F90')
        test_unit.add_fortran_dependency('bar', 'baz')
        self._check_ws(test_unit,
                       expected_unit,
                       expected_filename,
                       expected_dependency)

        # Add a third file also containing a third program unit and another
        # copy of the first.
        #
        # The new unit depends on two other units.
        #
        expected_unit = {'foo': [tmp_path / 'foo.f90', tmp_path / 'baz.F90'],
                         'bar': [tmp_path / 'bar.F90'],
                         'baz': [tmp_path / 'baz.F90'],
                         '!qux': []}
        expected_filename = {tmp_path / 'foo.f90': ['foo'],
                             tmp_path / 'bar.F90': ['bar'],
                             tmp_path / 'baz.F90': ['baz', 'foo'],
                             tmp_path / 'qux.f90.not': []}
        expected_dependency = {'foo': ['bar'],
                               'bar': ['baz'],
                               'baz': ['qux', 'cheese']}
        test_unit.add_fortran_program_unit('baz', tmp_path / 'baz.F90')
        test_unit.add_fortran_program_unit('foo', tmp_path / 'baz.F90')
        test_unit.add_fortran_dependency('baz', 'qux')
        test_unit.add_fortran_dependency('baz', 'cheese')
        self._check_ws(test_unit,
                       expected_unit,
                       expected_filename,
                       expected_dependency)

        # Remove a previously added file
        expected_unit = {'foo': [tmp_path / 'foo.f90'],
                         'bar': [tmp_path / 'bar.F90'],
                         '!baz': []}
        expected_filename = {tmp_path / 'foo.f90': ['foo'],
                             tmp_path / 'bar.F90': ['bar'],
                             tmp_path / 'baz.F90.not': []}
        test_unit.remove_fortran_file(tmp_path / 'baz.F90')
        expected_dependency = {'foo': ['bar'],
                               'bar': ['baz']}
        self._check_ws(test_unit,
                       expected_unit,
                       expected_filename,
                       expected_dependency)

    def test_unit_iterator(self, tmp_path):
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        test_unit.add_fortran_program_unit('foo', tmp_path / 'foo.f90')
        test_unit.add_fortran_program_unit('bar', tmp_path / 'bar.F90')
        test_unit.add_fortran_program_unit('baz', tmp_path / 'baz.f90')
        test_unit.add_fortran_program_unit('foo', tmp_path / 'baz.f90')

        expected = [('bar', [tmp_path / 'bar.F90']),
                    ('baz', [tmp_path / 'baz.f90']),
                    ('foo', [tmp_path / 'baz.f90', tmp_path / 'foo.f90'])]

        assert list(test_unit.iterate_program_units()) == expected


class DummyReader(TextReader):
    @property
    def filename(self) -> Union[Path, str]:
        return '<dummy>'

    def line_by_line(self) -> Iterator[str]:
        yield '! This comment should be removed and the line with it'
        yield "write(6, '(A)') 'Look! The end of this line will be removed'"
        yield '     ! Another line to be removed despite leading spaces'
        yield '  call the_thing( first,  &'
        yield '                  second, &'
        yield '                  third )'


class TestFortranNormaliser(object):
    def test_iteration(self):
        test_unit = FortranNormaliser(DummyReader())
        result = []
        for line in test_unit.line_by_line():
            result.append(line)
        assert result == ["write(6, '(A)') 'Look",
                          ' call the_thing( first, second, third )']


class TestFortranAnalyser(object):
    def test_analyser_program_units(self, caplog, tmp_path):
        '''
        Tests that program units and the "uses" they contain are correctly
        identified.
        '''
        caplog.set_level(logging.DEBUG)

        test_file: Path = tmp_path / 'test.f90'
        test_file.write_text(
            dedent('''
                   program foo
                     use iso_fortran_env, only : output
                     use, intrinsic :: ios_c_binding
                     use beef_mod
                     implicit none
                   end program foo

                   module bar
                     use iso_fortran_env, only : output
                     use, intrinsic :: ios_c_binding
                     use cheese_mod, only : bits_n_bobs
                     implicit none
                   end module bar

                   function baz(first, second)
                     use iso_fortran_env, only : output
                     use, intrinsic :: ios_c_binding
                     use teapot_mod
                     implicit none
                   end function baz

                   subroutine qux()
                     use iso_fortran_env, only : output
                     use, intrinsic :: ios_c_binding
                     use wibble_mod
                     use wubble_mod, only: stuff_n_nonsense
                     implicit none
                   end subroutine qux
                   '''))
        units: List[str] = ['foo', 'bar', 'baz', 'qux']
        prereqs: Dict[str, List[str]] = {'foo': ['beef_mod'],
                                         'bar': ['cheese_mod'],
                                         'baz': ['teapot_mod'],
                                         'qux': ['wibble_mod', 'wubble_mod']}

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(test_file), database)
        test_unit.run()
        working_state = FortranWorkingState(database)
        assert working_state.program_units_from_file(test_file) == units
        for unit in units:
            assert working_state.filenames_from_program_unit(unit) \
                == [test_file]
            assert working_state.depends_on(unit) == prereqs[unit]

    def test_analyser_scope(self, caplog, tmp_path):
        '''
        Tests that the analyser is able to track scope correctly.
        '''
        caplog.set_level(logging.DEBUG)

        test_file: Path = tmp_path / 'test.f90'
        test_file.write_text(
            dedent('''
                   program fred

                     implicit none

                     if (something) then
                       named: do i=1, 10
                       end do named
                     endif

                   contains

                     subroutine yabadabadoo()
                     end

                   end program

                   module barney

                     implicit none

                     type betty_type
                       integer :: property
                     contains
                       procedure inspect
                     end type

                     interface betty_type
                       procedure betty_constructor
                     end

                   contains

                     function inspect(this)
                       class(betty_type), intent(in) :: this
                       integer :: inspect
                       inspect = this%property
                     end function inspect

                   end module
                   '''))
        units: List[str] = ['fred', 'barney']

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(test_file), database)
        test_unit.run()
        working_state = FortranWorkingState(database)
        assert working_state.program_units_from_file(test_file) == units
        for unit in units:
            assert working_state.filenames_from_program_unit(unit) \
                == [test_file]

    def test_harvested_data(self, caplog, tmp_path):
        '''
        Checks that the analyser deals with rescanning a file.
        '''
        caplog.set_level(logging.DEBUG)

        first_file: Path = tmp_path / 'other.F90'
        first_file.write_text(
            dedent('''
                   program betty
                     use barney_mod, only :: dino
                     implicit none
                   end program betty

                   module barney_mod
                   end module barney_mod
                   '''))
        second_file: Path = tmp_path / 'test.f90'
        second_file.write_text(
            dedent('''
                   module barney_mod
                   end module barney_mod
                   '''))

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(first_file), database)
        test_unit.run()
        test_unit = FortranAnalyser(FileTextReader(second_file), database)
        test_unit.run()

        fdb = FortranWorkingState(database)
        assert list(fdb.iterate_program_units()) \
            == [('barney_mod', [first_file, second_file]),
                ('betty', [first_file])]
        assert fdb.depends_on('betty') == ['barney_mod']

        # Repeat the scan of second_file, there should be no change.
        #
        test_unit = FortranAnalyser(FileTextReader(second_file), database)
        test_unit.run()

        fdb = FortranWorkingState(database)
        assert list(fdb.iterate_program_units()) \
            == [('barney_mod', [first_file, second_file]),
                ('betty', [first_file])]
        assert fdb.depends_on('betty') == ['barney_mod']

    def test_naked_use(self, tmp_path):
        '''
        Ensures that an exception is raised if a "use" is found outside a
        program unit.
        '''
        test_file: Path = tmp_path / 'test.f90'
        test_file.write_text(
            dedent('''
                   use beef_mod

                   module test_mod
                   end module test_mod
                   '''))

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(test_file), database)
        with pytest.raises(TaskException):
            test_unit.run()

    def test_mismatched_block_end(self, tmp_path: Path):
        """
        Ensure that the analyser handles mismatched block ends correctly.
        """
        source = """
        module wibble_mod
        contains
          type :: thing_type
          end if
        end module wibble_mod
        """
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(StringTextReader(source),
                                    database)
        with pytest.raises(TaskException):
            test_unit.run()

    def test_mismatched_end_name(self, tmp_path: Path):
        """
        Ensure that the analyser handles mismatched block end names correctly.
        """
        source = """
        module wibble_mod
          type :: thing_type
          end type blasted_type
        end module wibble_mod
        """
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(StringTextReader(source),
                                    database)
        with pytest.raises(TaskException):
            test_unit.run()


class TestFortranPreProcessor(object):
    def test_preprocssor_output(self, caplog, tmp_path):
        '''
        Tests that the processor correctly applies to the source.
        '''
        caplog.set_level(logging.DEBUG)

        test_file: Path = tmp_path / 'test.F90'
        test_file.write_text(
            dedent('''
                   #if defined(TEST_MACRO)
                   SUBROUTINE included_when_test_macro_set()
                   IMPLICIT NONE
                   END SUBROUTINE included_when_test_macro_set
                   #else
                   SUBROUTINE included_when_test_macro_not_set()
                   IMPLICIT NONE
                   END SUBROUTINE included_when_test_macro_not_set
                   #endif
                   #if !defined(TEST_MACRO)
                   FUNCTION included_when_test_macro_not_set()
                   IMPLICIT NONE
                   END FUNCTION included_when_test_macro_not_set
                   #else
                   FUNCTION included_when_test_macro_set()
                   IMPLICIT NONE
                   END FUNCTION included_when_test_macro_set
                   #endif
                   '''))
        # Test once with the macro set
        preprocessor = FortranPreProcessor(
                test_file,
                tmp_path,
                ['-DTEST_MACRO=test_macro', ])
        test_unit = CommandTask(preprocessor)
        test_unit.run()

        assert preprocessor.output[0].exists
        with preprocessor.output[0].open('r') as outfile:
            outfile_content = outfile.read().strip()

        assert outfile_content == dedent('''\
                   SUBROUTINE included_when_test_macro_set()
                   IMPLICIT NONE
                   END SUBROUTINE included_when_test_macro_set
                   FUNCTION included_when_test_macro_set()
                   IMPLICIT NONE
                   END FUNCTION included_when_test_macro_set''')

        # And test again with the macro unset
        preprocessor = FortranPreProcessor(
                test_file,
                tmp_path,
                [])
        test_unit = CommandTask(preprocessor)
        test_unit.run()

        assert preprocessor.output[0].exists
        with preprocessor.output[0].open('r') as outfile:
            outfile_content = outfile.read().strip()

        assert outfile_content == dedent('''\
                   SUBROUTINE included_when_test_macro_not_set()
                   IMPLICIT NONE
                   END SUBROUTINE included_when_test_macro_not_set
                   FUNCTION included_when_test_macro_not_set()
                   IMPLICIT NONE
                   END FUNCTION included_when_test_macro_not_set''')


class TestFortranCompiler(object):
    def test_constructor(self):
        test_unit = FortranCompiler(Path('input.f90'),
                                    Path('workspace'),
                                    ['flag1', 'flag2'],
                                    [Path('prereq1.mod'),
                                     Path('prereq2.mod')])
        assert test_unit.input == [Path('prereq1.mod'),
                                   Path('prereq2.mod'),
                                   Path('input.f90')]
        assert test_unit.output == [Path('workspace/input.o')]
        assert test_unit.as_list == ['gfortran', '-c', '-Jworkspace',
                                     'flag1', 'flag2', 'input.f90',
                                     '-o', 'workspace/input.o']


class TestFortranLinker(object):
    def test_constructor(self):
        test_unit = FortranLinker(Path('workspace'),
                                  ['flag3', 'flag4'],
                                  Path('bin/output'))
        test_unit.add_object(Path('an.o'))
        assert test_unit.input == [Path('an.o')]
        assert test_unit.output == [Path('bin/output')]
        assert test_unit.as_list == ['gfortran', '-o', 'bin/output',
                                     'flag3', 'flag4', 'an.o']

    def test_add_object(self):
        test_unit = FortranLinker(Path('deepspace'),
                                  [],
                                  Path('bin/dusty'))
        with pytest.raises(TaskException):
            _ = test_unit.as_list

        test_unit.add_object(Path('foo.o'))
        assert test_unit.as_list == ['gfortran', '-o', 'bin/dusty',
                                     'foo.o']

        test_unit.add_object(Path('bar.o'))
        assert test_unit.as_list == ['gfortran', '-o', 'bin/dusty',
                                     'foo.o', 'bar.o']

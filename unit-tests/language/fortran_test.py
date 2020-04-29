##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
from pathlib import Path
from textwrap import dedent
from typing import Iterator, Union

import pytest  # type: ignore

from fab.database import SqliteStateDatabase, WorkingStateException
from fab.language import CommandTask, TaskException
from fab.language.fortran import (FortranAnalyser,
                                  FortranCompiler,
                                  FortranInfo,
                                  FortranLinker,
                                  FortranNormaliser,
                                  FortranPreProcessor,
                                  FortranUnitID,
                                  FortranUnitUnresolvedID,
                                  FortranWorkingState)
from fab.reader import FileTextReader, StringTextReader, TextReader


class TestFortranUnitUnresolvedID:
    def test_constructor(self):
        test_unit = FortranUnitUnresolvedID('thumper')
        assert test_unit.name == 'thumper'

    def test_equality(self):
        test_unit = FortranUnitUnresolvedID('dumper')
        with pytest.raises(TypeError):
            _ = test_unit == 'Not a FortranUnitUnresolvedID'

        other = FortranUnitUnresolvedID('dumper')
        assert test_unit == other
        assert other == test_unit

        other = FortranUnitUnresolvedID('trumper')
        assert test_unit != other
        assert other != test_unit


class TestFortranUnitID:
    def test_constructor(self):
        test_unit = FortranUnitID('beef', Path('cheese'))
        assert test_unit.name == 'beef'
        assert test_unit.found_in == Path('cheese')

    def test_hash(self):
        test_unit = FortranUnitID('grumper', Path('bumper'))
        similar = FortranUnitID('grumper', Path('bumper'))
        different = FortranUnitID('bumper', Path('grumper'))
        assert hash(test_unit) == hash(similar)
        assert hash(test_unit) != hash(different)

    def test_equality(self):
        test_unit = FortranUnitID('salt', Path('pepper'))
        with pytest.raises(TypeError):
            _ = test_unit == 'Not a FortranUnitID'

        other = FortranUnitID('salt', Path('pepper'))
        assert test_unit == other
        assert other == test_unit

        other = FortranUnitID('stew', Path('dumplings'))
        assert test_unit != other
        assert other != test_unit


class TestFortranInfo:
    def test_default_constructor(self):
        test_unit \
            = FortranInfo(FortranUnitID('argle',
                                        Path('bargle/wargle.gargle')))
        assert test_unit.unit.name == 'argle'
        assert test_unit.unit.found_in == Path('bargle/wargle.gargle')
        assert test_unit.depends_on == []

    def test_prereq_constructor(self):
        test_unit \
            = FortranInfo(FortranUnitID('argle',
                                        Path('bargle/wargle.gargle')),
                          ['cheese'])
        assert test_unit.unit.name == 'argle'
        assert test_unit.unit.found_in == Path('bargle/wargle.gargle')
        assert test_unit.depends_on == ['cheese']

    def test_equality(self):
        test_unit \
            = FortranInfo(FortranUnitID('argle',
                                        Path('bargle/wargle.gargle')),
                          ['beef', 'cheese'])
        with pytest.raises(TypeError):
            _ = test_unit == 'not a FortranInfo'

        other = FortranInfo(FortranUnitID('argle',
                                          Path('bargle/wargle.gargle')),
                            ['beef', 'cheese'])
        assert test_unit == other
        assert other == test_unit

        other = FortranInfo(FortranUnitID('argle',
                                          Path('bargle/wargle.gargle')))
        assert test_unit != other
        assert other != test_unit

    def test_add_prerequisite(self):
        test_unit \
            = FortranInfo(FortranUnitID('argle',
                                        Path('bargle/wargle.gargle')))
        assert test_unit.depends_on == []

        test_unit.add_prerequisite('cheese')
        assert test_unit.depends_on == ['cheese']


class TestFortranWorkingSpace:
    def test_add_remove_sequence(self, tmp_path: Path):
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)
        assert list(iter(test_unit)) == []

        # Add a file containing a program unit and an unsatisfied dependency.
        #
        test_unit.add_fortran_program_unit(FortranUnitID('foo',
                                                         Path('foo.f90')))
        test_unit.add_fortran_dependency(FortranUnitID('foo',
                                                       Path('foo.f90')),
                                         'bar')
        assert list(iter(test_unit)) \
            == [FortranInfo(FortranUnitID('foo', Path('foo.f90')),
                            ['bar'])]
        assert list(test_unit.depends_on(FortranUnitID('foo',
                                                       Path('foo.f90')))) \
            == [FortranUnitUnresolvedID('bar')]

        # Add a second file containing a second program unit.
        #
        # This satisfies the previously dangling dependency and adds a new
        # one.
        #
        test_unit.add_fortran_program_unit(FortranUnitID('bar',
                                                         Path('bar.F90')))
        test_unit.add_fortran_dependency(FortranUnitID('bar',
                                                       Path('bar.F90')),
                                         'baz')
        assert list(iter(test_unit)) \
            == [FortranInfo(FortranUnitID('bar', Path('bar.F90')),
                            ['baz']),
                FortranInfo(FortranUnitID('foo', Path('foo.f90')),
                            ['bar'])]
        assert list(test_unit.depends_on(FortranUnitID('foo',
                                                       Path('foo.f90')))) \
            == [FortranUnitID('bar', Path('bar.F90'))]
        assert list(test_unit.depends_on(FortranUnitID('bar',
                                                       Path('bar.F90')))) \
            == [FortranUnitUnresolvedID('baz')]

        # Add a third file also containing a third program unit and another
        # copy of the first.
        #
        # The new unit depends on two other units.
        #
        test_unit.add_fortran_program_unit(FortranUnitID('baz',
                                                         Path('baz.F90')))
        test_unit.add_fortran_program_unit(FortranUnitID('foo',
                                                         Path('baz.F90')))
        test_unit.add_fortran_dependency(FortranUnitID('baz',
                                                       Path('baz.F90')),
                                         'qux')
        test_unit.add_fortran_dependency(FortranUnitID('baz',
                                                       Path('baz.F90')),
                                         'cheese')
        assert list(iter(test_unit)) \
            == [FortranInfo(FortranUnitID('bar', Path('bar.F90')),
                            ['baz']),
                FortranInfo(FortranUnitID('baz', Path('baz.F90')),
                            ['cheese', 'qux']),
                FortranInfo(FortranUnitID('foo', Path('baz.F90'))),
                FortranInfo(FortranUnitID('foo', Path('foo.f90')),
                            ['bar'])]
        assert list(test_unit.depends_on(FortranUnitID('foo',
                                                       Path('foo.f90')))) \
            == [FortranUnitID('bar', Path('bar.F90'))]
        assert list(test_unit.depends_on(FortranUnitID('foo',
                                                       Path('baz.F90')))) \
            == []
        assert list(test_unit.depends_on(FortranUnitID('bar',
                                                       Path('bar.F90')))) \
            == [FortranUnitID('baz', Path('baz.F90'))]
        assert list(test_unit.depends_on(FortranUnitID('baz',
                                                       Path('baz.F90')))) \
            == [FortranUnitUnresolvedID('qux'),
                FortranUnitUnresolvedID('cheese')]

        # Remove a previously added file
        #
        test_unit.remove_fortran_file(Path('baz.F90'))
        assert list(iter(test_unit)) \
            == [FortranInfo(FortranUnitID('bar', Path('bar.F90')),
                            ['baz']),
                FortranInfo(FortranUnitID('foo', Path('foo.f90')),
                            ['bar'])]
        assert list(test_unit.depends_on(FortranUnitID('foo',
                                                       Path('foo.f90')))) \
            == [FortranUnitID('bar', Path('bar.F90'))]
        assert list(test_unit.depends_on(FortranUnitID('bar',
                                                       Path('bar.F90')))) \
            == [FortranUnitUnresolvedID('baz')]

    def test_get_program_unit(self, tmp_path: Path):
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        # Test on an empty list
        #
        with pytest.raises(WorkingStateException):
            _ = test_unit.get_program_unit('tigger')

        # Test we can retrieve an item from a single element list
        test_unit.add_fortran_program_unit(FortranUnitID('tigger',
                                                         Path('tigger.f90')))
        assert test_unit.get_program_unit('tigger') \
            == [FortranInfo(FortranUnitID('tigger', Path('tigger.f90')))]
        with pytest.raises(WorkingStateException):
            _ = test_unit.get_program_unit('eeor')

        # Test retrieval from a multi-element list and with prerequisites.
        #
        test_unit.add_fortran_program_unit(FortranUnitID('eeor',
                                                         Path('eeor.f90')))
        test_unit.add_fortran_dependency(FortranUnitID('eeor',
                                                       Path('eeor.f90')),
                                         'pooh')
        test_unit.add_fortran_dependency(FortranUnitID('eeor',
                                                       Path('eeor.f90')),
                                         'piglet')
        assert test_unit.get_program_unit('tigger') \
            == [FortranInfo(FortranUnitID('tigger', Path('tigger.f90')))]
        assert test_unit.get_program_unit('eeor') \
            == [FortranInfo(FortranUnitID('eeor', Path('eeor.f90')),
                            ['piglet', 'pooh'])]
        with pytest.raises(WorkingStateException):
            _ = test_unit.get_program_unit('pooh')

        # Test a multiply defined program unit.
        #
        test_unit.add_fortran_program_unit(FortranUnitID('tigger',
                                                         Path('hundred.f90')))
        assert test_unit.get_program_unit('tigger') \
            == [FortranInfo(FortranUnitID('tigger', Path('hundred.f90'))),
                FortranInfo(FortranUnitID('tigger', Path('tigger.f90')))]
        assert test_unit.get_program_unit('eeor') \
            == [FortranInfo(FortranUnitID('eeor', Path('eeor.f90')),
                            ['piglet', 'pooh'])]
        with pytest.raises(WorkingStateException):
            _ = test_unit.get_program_unit('pooh')


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

    def test_get_unit_info(self, tmp_path):
        database = SqliteStateDatabase(tmp_path)
        test_unit = FortranWorkingState(database)

        test_unit.add_fortran_program_unit(FortranUnitID('foo',
                                                         tmp_path / 'foo.f90'))
        test_unit.add_fortran_program_unit(FortranUnitID('bar',
                                                         tmp_path / 'bar.F90'))
        test_unit.add_fortran_program_unit(FortranUnitID('bar',
                                                         tmp_path / 'brb.f90'))
        test_unit.add_fortran_program_unit(FortranUnitID('baz',
                                                         tmp_path / 'baz.f90'))
        test_unit.add_fortran_dependency(FortranUnitID('bar',
                                                       tmp_path / 'brb.f90'),
                                         'foo')
        test_unit.add_fortran_dependency(FortranUnitID('baz',
                                                       tmp_path / 'baz.f90'),
                                         'foo')
        test_unit.add_fortran_dependency(FortranUnitID('baz',
                                                       tmp_path / 'baz.f90'),
                                         'bar')

        assert test_unit.get_program_unit('foo') \
            == [FortranInfo(FortranUnitID('foo', tmp_path/'foo.f90'))]
        assert test_unit.get_program_unit('bar') \
            == [FortranInfo(FortranUnitID('bar', tmp_path/'bar.F90')),
                FortranInfo(FortranUnitID('bar', tmp_path/'brb.f90'),
                            ['foo'])]
        assert test_unit.get_program_unit('baz') \
            == [FortranInfo(FortranUnitID('baz', tmp_path/'baz.f90'),
                            ['bar', 'foo'])]


class TestFortranAnalyser(object):
    def test_analyser_program_units(self, caplog, tmp_path):
        """
        Tests that program units and the "uses" they contain are correctly
        identified.
        """
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

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(test_file), database)
        test_unit.run()
        working_state = FortranWorkingState(database)
        assert list(working_state) \
            == [FortranInfo(FortranUnitID('bar', tmp_path/'test.f90'),
                            ['cheese_mod']),
                FortranInfo(FortranUnitID('baz', tmp_path/'test.f90'),
                            ['teapot_mod']),
                FortranInfo(FortranUnitID('foo', tmp_path/'test.f90'),
                            ['beef_mod']),
                FortranInfo(FortranUnitID('qux', tmp_path/'test.f90'),
                            ['wibble_mod', 'wubble_mod'])]

    def test_analyser_scope(self, caplog, tmp_path):
        """
        Tests that the analyser is able to track scope correctly.
        """
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

        database: SqliteStateDatabase = SqliteStateDatabase(tmp_path)
        test_unit = FortranAnalyser(FileTextReader(test_file), database)
        test_unit.run()
        working_state = FortranWorkingState(database)
        assert list(working_state) \
            == [FortranInfo(FortranUnitID('barney', tmp_path/'test.f90'), []),
                FortranInfo(FortranUnitID('fred', tmp_path/'test.f90'), [])]

    def test_harvested_data(self, caplog, tmp_path):
        """
        Checks that the analyser deals with rescanning a file.
        """
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
        assert list(iter(fdb)) \
            == [FortranInfo(FortranUnitID('barney_mod', first_file)),
                FortranInfo(FortranUnitID('barney_mod', second_file)),
                FortranInfo(FortranUnitID('betty', first_file),
                            ['barney_mod'])]
        assert list(fdb.depends_on(FortranUnitID('betty', first_file))) \
            == [FortranUnitID('barney_mod', tmp_path / 'other.F90'),
                FortranUnitID('barney_mod', tmp_path / 'test.f90')]

        # Repeat the scan of second_file, there should be no change.
        #
        test_unit = FortranAnalyser(FileTextReader(second_file), database)
        test_unit.run()

        fdb = FortranWorkingState(database)
        assert list(iter(fdb)) \
            == [FortranInfo(FortranUnitID('barney_mod', first_file)),
                FortranInfo(FortranUnitID('barney_mod', second_file)),
                FortranInfo(FortranUnitID('betty', first_file),
                            ['barney_mod'])]
        assert list(fdb.depends_on(FortranUnitID('betty', first_file))) \
            == [FortranUnitID('barney_mod', tmp_path / 'other.F90'),
                FortranUnitID('barney_mod', tmp_path / 'test.f90')]

    def test_naked_use(self, tmp_path):
        """
        Ensures that an exception is raised if a "use" is found outside a
        program unit.
        """
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
        """
        Tests that the processor correctly applies to the source.
        """
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

# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

'''
Fortran language handling classes.
'''
import logging
from pathlib import Path
import re
import sqlite3
from typing import Generator, List, Match, Optional, Pattern, Sequence, Tuple

from fab.database import StateDatabase, WorkingStateException
from fab.language import Analyser, AnalysisException


class FortranWorkingState(object):
    def __init__(self, database: StateDatabase):
        self._database: StateDatabase = database
        # According to the Fortran spec, section 3.2.2 in
        # BS ISO/IEC 1539-1:2010, the maximum size of a name is 63 characters.
        # Choosing a length for filenames is much less clear cut. I have gone
        # for 1k.
        #
        self._database.connection.execute(
            '''create table if not exists fortran_unit (
                 id integer primary key,
                 unit character(63) not null,
                 filename character(1024) not null
               )'''
        )
        self._database.connection.execute(
            'create index if not exists idx_fortran_program_unit '
            'on fortran_unit(unit)')
        self._database.connection.execute(
            'create index if not exists idx_fortran_filename '
            'on fortran_unit(filename)')
        self._database.connection.commit()

    def add_fortran_program_unit(self, name: str, in_file: Path) -> None:
        '''
        Creates a record of a new program unit and the file it is found in.

        Note that the filename is absolute meaning that if you rename or move
        the source directory nothing will match up.

        :param name: Program unit name.
        :param in_file: Filename of source containing program unit.
        '''
        self._database.connection.execute(
            '''insert into fortran_unit (unit, filename)
               values (:unit, :filename)''',
            {'unit': name, 'filename': str(in_file)})
        self._database.connection.commit()

    def remove_fortran_file(self, filename: Path) -> None:
        '''
        Removes all records relating of a particular source file.

        :param filename: File to be removed.
        '''
        self._database.connection.execute(
            'delete from fortran_unit where filename=:filename',
            {'filename': str(filename)})
        self._database.connection.commit()

    def iterate_program_units(self) \
            -> Generator[Tuple[str, Sequence[Path]], None, None]:
        '''
        Yields all units and their containing file names.

        :return: Unit name and containing filename pairs.
        '''
        cursor: sqlite3.Cursor = self._database.connection.execute(
            'select unit, filename from fortran_unit '
            'order by unit, filename')
        unit = None
        files = []
        while True:
            row: sqlite3.Row = cursor.fetchone()
            if row is None:
                break
            if row['unit'] != unit:
                if unit is not None:
                    yield (unit, files)
                unit = row['unit']
                files = [Path(row['filename'])]
            else:  # row['unit'] == unit
                files.append(Path(row['filename']))
        if unit is not None:
            yield (unit, files)

    def filenames_from_program_unit(self, name: str) -> List[Path]:
        '''
        Gets the source files in which a program unit may be found.

        It is possible that the same program unit is multiply defined, hence
        why a list is returned. It would be an error to try linking these into
        a single executable but that is not a concern for the model of the
        source tree.

        :param name: Program unit name.
        :return: Filenames of source files.
        '''
        filenames: List[Path] = []
        cursor: sqlite3.Cursor = self._database.connection.execute(
            'select filename from fortran_unit where unit=:unit',
            {'unit': name})
        while True:
            row: sqlite3.Row = cursor.fetchone()
            if row is None:
                break
            filenames.append(Path(row['filename']))
        cursor.close()
        if len(filenames) == 0:
            message = 'Program unit "{unit}" not found in database.'
            raise WorkingStateException(message.format(unit=name))
        return filenames

    def program_units_from_file(self, filename: Path) -> List[str]:
        '''
        Gets the program units found in a particular source file.

        :param filename: Source file of interest.
        :return: Program units found therein.
        '''
        units: List[str] = []
        cursor: sqlite3.Cursor = self._database.connection.execute(
            'select unit from fortran_unit where filename=:filename ',
            {'filename': str(filename)})
        while True:
            row: sqlite3.Row = cursor.fetchone()
            if row is None:
                break
            units.append(row['unit'])
        cursor.close()
        if len(units) == 0:
            message = 'Source file "{filename}" not found in database.'
            raise WorkingStateException(message.format(filename=filename))
        return units


class FortranAnalyser(Analyser):
    def __init__(self, database: StateDatabase):
        super().__init__(database)
        self._state = FortranWorkingState(database)

    _letters: str = r'abcdefghijklmnopqrstuvwxyz'
    _digits: str = r'1234567890'
    _underscore: str = r'_'
    _alphanumeric_re: str = '[' + _letters + _digits + _underscore + ']'
    _name_re: str = '[' + _letters + ']' + _alphanumeric_re + '*'
    _unit_block_re: str = r'program|module|function|subroutine'
    _scope_block_re: str = r'associate|block|critical|do|if|select'
    _iface_block_re: str = r'interface'
    _type_block_re: str = r'type'

    _program_unit_re: str = r'^\s*({unit_type_re})\s*({name_re})' \
                            .format(unit_type_re=_unit_block_re,
                                    name_re=_name_re)
    _scoping_re: str = r'^\s*(({name_re})\s*:)?\s*({scope_type_re})' \
                       .format(scope_type_re=_scope_block_re,
                               name_re=_name_re)
    _interface_re: str = r'^\s*{iface_block_re}\s*({name_re})?' \
                         .format(iface_block_re=_iface_block_re,
                                 name_re=_name_re)
    _type_re: str = r'^\s*{type_block_re}' \
                    r'((\s*,\s*[^,]+)*\s*::)?' \
                    r'\s*({name_re})'.format(type_block_re=_type_block_re,
                                             name_re=_name_re)
    _end_block_re: str \
        = r'^\s*end' \
          r'\s*({scope_block_re}|{iface_block_re}' \
          r'|{type_block_re}|{unit_type_re})?' \
          r'\s*({name_re})?'.format(scope_block_re=_scope_block_re,
                                    iface_block_re=_iface_block_re,
                                    type_block_re=_type_block_re,
                                    unit_type_re=_unit_block_re,
                                    name_re=_name_re)

    _program_unit_pattern: Pattern = re.compile(_program_unit_re,
                                                re.IGNORECASE)
    _scoping_pattern: Pattern = re.compile(_scoping_re, re.IGNORECASE)
    _interface_pattern: Pattern = re.compile(_interface_re, re.IGNORECASE)
    _type_pattern: Pattern = re.compile(_type_re, re.IGNORECASE)
    _end_block_pattern: Pattern = re.compile(_end_block_re, re.IGNORECASE)

    def analyse(self, filename: Path) -> None:
        logger = logging.getLogger(__name__)

        self._state.remove_fortran_file(filename)

        scope: List[Tuple[str, str]] = []
        for line in self._normalise(filename):
            logger.debug(scope)
            logger.debug('Considering: %s', line)

            if len(scope) == 0:
                unit_match: Optional[Match] \
                    = self._program_unit_pattern.match(line)
                if unit_match:
                    unit_type: str = unit_match.group(1).lower()
                    unit_name: str = unit_match.group(2).lower()
                    logger.debug('Found %s called "%s"', unit_type, unit_name)
                    self._state.add_fortran_program_unit(unit_name, filename)
                    scope.append((unit_type, unit_name))
                continue

            block_match: Optional[Match] = self._scoping_pattern.match(line)
            if block_match:
                # Beware we want the value of a different group to the one we
                # check the presence of.
                #
                block_name: str = block_match.group(1) \
                                  and block_match.group(2).lower()
                block_nature: str = block_match.group(3).lower()
                logger.debug('Found %s called "%s"', block_nature, block_name)
                scope.append((block_nature, block_name))
                continue

            iface_match: Optional[Match] = self._interface_pattern.match(line)
            if iface_match:
                iface_name = iface_match.group(1) \
                             and iface_match.group(1).lower()
                logger.debug('Found interface called "%s"', iface_name)
                scope.append(('interface', iface_name))
                continue

            type_match: Optional[Match] = self._type_pattern.match(line)
            if type_match:
                type_name = type_match.group(3).lower()
                logger.debug('Found type called "%s"', type_name)
                scope.append(('type', type_name))
                continue

            end_match: Optional[Match] = self._end_block_pattern.match(line)
            if end_match:
                end_nature: str = end_match.group(1) \
                    and end_match.group(1).lower()
                end_name: str = end_match.group(2) \
                    and end_match.group(2).lower()
                logger.debug('Found end of %s called %s',
                             end_nature, end_name)
                exp: Tuple[str, str] = scope.pop()
                if end_nature is not None:
                    if end_nature != exp[0]:
                        message = 'Expected end of {exp} but found {found}'

                        raise AnalysisException(
                            message.format(exp=exp[0], found=end_nature))
                if end_name is not None:
                    if end_name != exp[1]:
                        message = '''
                        Expected end of {exp} "{name}" but found {found}
                        '''.strip()
                        raise AnalysisException(
                            message.format(exp=exp[0],
                                           name=exp[1],
                                           found=end_name))

    @staticmethod
    def _normalise(filename: Path) -> Generator[str, None, None]:
        '''
        Generator to return each line of a source file; the lines
        are sanitised to remove comments and collapse the result
        of continuation lines whilst also trimming away as much
        whitespace as possible
        '''
        with filename.open('r') as source:
            line_buffer = ''
            for line in source:
                # Remove comments - we accept that an exclamation mark
                # appearing in a string will cause the rest of that line
                # to be blanked out, but the things we wish to parse
                # later shouldn't appear after a string on a line anyway
                line = re.sub(r'!.*', '', line)

                # If the line is empty, go onto the next
                if line.strip() == '':
                    continue

                # Deal with continuations by removing them to collapse
                # the lines together
                line_buffer += line
                if "&" in line_buffer:
                    line_buffer = re.sub(r'&\s*\n', '', line_buffer)
                    continue

                # Before output, minimise whitespace but add a space on the end
                # of the line.
                line_buffer = re.sub(r'\s+', r' ', line_buffer)
                yield line_buffer.rstrip()
                line_buffer = ''

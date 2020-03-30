# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

'''
Fortran language handling classes.
'''
import logging
from pathlib import Path
import re
from typing import (Generator,
                    Iterator,
                    List,
                    Match,
                    Optional,
                    Pattern,
                    Tuple,
                    Union)

from fab.database import (DatabaseDecorator,
                          FileInfoDatabase,
                          StateDatabase,
                          SqliteStateDatabase,
                          WorkingStateException)
from fab.language import Analyser, TaskException, Command
from fab.reader import TextReader, TextReaderDecorator


class FortranWorkingState(DatabaseDecorator):
    '''
    Maintains a database of information relating to Fortran program units.
    '''
    # According to the Fortran spec, section 3.2.2 in
    # BS ISO/IEC 1539-1:2010, the maximum size of a name is 63 characters.
    #
    # If you find source containing labels longer than this then that source
    # is non-conformant.
    #
    _FORTRAN_LABEL_LENGTH: int = 63

    def __init__(self, database: StateDatabase):
        super().__init__(database)
        create_unit_table = [
            f'''create table if not exists fortran_unit (
                   id integer primary key,
                   unit character({self._FORTRAN_LABEL_LENGTH}) not null,
                   found_in character({FileInfoDatabase.PATH_LENGTH})
                       references file_info (filename)
                   )''',
            '''create index if not exists idx_fortran_program_unit
                   on fortran_unit(unit)''',
            '''create index if not exists idx_fortran_found_in
                   on fortran_unit(found_in)'''
        ]
        self.execute(create_unit_table, {})

        # Although the current unit will already have been entered into the
        # database it is not necessarily unique. We may have multiple source
        # files which define similarly named units. Thus it can not be used as
        # a foreign key.
        #
        # Meanwhile the dependency unit may not have been encountered yet so
        # we can't expect it to be in the database. Thus it too may not be
        # used as a foreign key.
        #
        create_prerequisite_table = [
            f'''create table if not exists fortran_prerequisite (
                  id integer primary key,
                  dependor character({self._FORTRAN_LABEL_LENGTH}) not null,
                  dependee character({self._FORTRAN_LABEL_LENGTH}) not null
                  )''',
            '''create index if not exists idx_fortran_dependor
                 on fortran_prerequisite(dependor)''',
            '''create index if not exists idx_fortran_dependee
                 on fortran_prerequisite(dependee)'''
        ]
        self.execute(create_prerequisite_table, {})

    def add_fortran_program_unit(self, name: str,
                                 in_file: Union[Path, str]) -> None:
        '''
        Creates a record of a new program unit and the file it is found in.

        Note that the filename is absolute meaning that if you rename or move
        the source directory nothing will match up.

        :param name: Program unit name.
        :param in_file: Filename of source containing program unit.
        '''
        add_unit = [
            '''insert into fortran_unit (unit, found_in)
                   values (:unit, :filename)'''
        ]
        self.execute(add_unit, {'unit': name, 'filename': str(in_file)})

    def add_fortran_dependency(self, unit: str, depends_on: str) -> None:
        '''
        Records the dependency of one unit on another.

        :param unit: Name of the depending unit.
        :param depends_on:  Name of the prerequisite unit.
        '''
        add_dependency = [
            '''insert into fortran_prerequisite(dependor, dependee)
                   values (:unit, :depends_on)'''
        ]
        self.execute(add_dependency, {'unit': unit, 'depends_on': depends_on})

    def remove_fortran_file(self, filename: Union[Path, str]) -> None:
        '''
        Removes all records relating of a particular source file.

        :param filename: File to be removed.
        '''
        remove_file = [
            '''delete from fortran_prerequisite
                   where dependor=(select unit from fortran_unit
                       where found_in=:filename)''',
            '''delete from fortran_unit where found_in=:filename'''
            ]
        self.execute(remove_file, {'filename': str(filename)})

    def iterate_program_units(self) -> Generator[Tuple[str, Path], None, None]:
        '''
        Yields all units and their containing file name.

        :return: Unit name and containing filename pairs.
        '''
        query = '''select unit, found_in from fortran_unit
                       order by unit, found_in'''
        rows = self.execute(query, {})
        for row in rows:
            yield row['unit'], Path(row['found_in'])

    def filenames_from_program_unit(self, name: str) -> List[Path]:
        '''
        Gets the source files in which a program unit may be found.

        It is possible that similarly named program units appear in multiple
        files, hence why a list is returned. It would be an error to try
        linking these into a single executable but that is not a concern for
        the model of the source tree.

        :param name: Program unit name.
        :return: Filenames of source files.
        '''
        query = 'select found_in from fortran_unit where unit=:unit'
        rows = self.execute(query, {'unit': name})
        filenames: List[Path] = []
        for row in rows:
            filenames.append(Path(row['found_in']))
        if len(filenames) == 0:
            message = 'Program unit "{unit}" not found in database.'
            raise WorkingStateException(message.format(unit=name))
        return filenames

    def program_units_from_file(self, filename: Path) -> List[str]:
        '''
        Gets the program units found in a particular source file. There may be
        More than one.

        :param filename: Source file of interest.
        :return: Program units found therein.
        '''
        query = 'select unit from fortran_unit where found_in=:filename'
        rows = self.execute(query, {'filename': str(filename)})
        units: List[str] = []
        for row in rows:
            units.append(row['unit'])
        if len(units) == 0:
            message = 'Source file "{filename}" not found in database.'
            raise WorkingStateException(message.format(filename=filename))
        return units

    def depends_on(self, unit: str) -> List[str]:
        '''
        Gets the prerequisite program units of a program unit.

        :param unit: Program unit name
        :return: Prerequisite unit names. May be an empty list.
        '''
        query = '''select dependee
                   from fortran_prerequisite
                   where dependor=:unit'''
        rows = self.execute(query, {'unit': unit})
        units: List[str] = []
        for row in rows:
            units.append(row['dependee'])
        return units


class _FortranNormaliser(TextReaderDecorator):
    def __init__(self, source: TextReader):
        super().__init__(source)
        self._line_buffer = ''

    def line_by_line(self) -> Iterator[str]:
        '''
        Each line of the source file is modified to ease the work of analysis.

        The lines are sanitised to remove comments and collapse the result
        of continuation lines whilst also trimming away as much whitespace as
        possible
        '''
        for line in self._source.line_by_line():
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
            self._line_buffer += line
            if '&' in self._line_buffer:
                self._line_buffer = re.sub(r'&\s*\n', '', self._line_buffer)
                continue

            # Before output, minimise whitespace but add a space on the end
            # of the line.
            line_buffer = re.sub(r'\s+', r' ', self._line_buffer)
            yield line_buffer.rstrip()
            self._line_buffer = ''


class FortranAnalyser(Analyser):
    def __init__(self, reader: TextReader, database: SqliteStateDatabase):
        super().__init__(reader, database)
        self._state = FortranWorkingState(database)

    _intrinsic_modules = ['iso_fortran_env']

    _letters: str = r'abcdefghijklmnopqrstuvwxyz'
    _digits: str = r'1234567890'
    _underscore: str = r'_'
    _alphanumeric_re: str = '[' + _letters + _digits + _underscore + ']'
    _name_re: str = '[' + _letters + ']' + _alphanumeric_re + '*'
    _procedure_block_re: str = r'function|subroutine'
    _unit_block_re: str = r'program|module|' + _procedure_block_re
    _scope_block_re: str = r'associate|block|critical|do|if|select'
    _iface_block_re: str = r'interface'
    _type_block_re: str = r'type'

    _program_unit_re: str = r'^\s*({unit_type_re})\s*({name_re})' \
                            .format(unit_type_re=_unit_block_re,
                                    name_re=_name_re)
    _scoping_re: str = r'^\s*(({name_re})\s*:)?\s*({scope_type_re})' \
                       .format(scope_type_re=_scope_block_re,
                               name_re=_name_re)
    _procedure_re: str = r'^\s*({procedure_block_re})\s*({name_re})' \
                         .format(procedure_block_re=_procedure_block_re,
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

    _use_statement_re: str \
        = r'^\s*use((\s*,\s*non_intrinsic)?\s*::)?\s*({name_re})' \
          .format(name_re=_name_re)

    _program_unit_pattern: Pattern = re.compile(_program_unit_re,
                                                re.IGNORECASE)
    _scoping_pattern: Pattern = re.compile(_scoping_re, re.IGNORECASE)
    _procedure_pattern: Pattern = re.compile(_procedure_re, re.IGNORECASE)
    _interface_pattern: Pattern = re.compile(_interface_re, re.IGNORECASE)
    _type_pattern: Pattern = re.compile(_type_re, re.IGNORECASE)
    _end_block_pattern: Pattern = re.compile(_end_block_re, re.IGNORECASE)
    _use_pattern: Pattern = re.compile(_use_statement_re, re.IGNORECASE)

    def run(self) -> List[Path]:
        logger = logging.getLogger(__name__)

        self._state.remove_fortran_file(self._reader.filename)

        normalised_source = _FortranNormaliser(self._reader)
        scope: List[Tuple[str, str]] = []
        for line in normalised_source.line_by_line():
            logger.debug(scope)
            logger.debug('Considering: %s', line)

            if len(scope) == 0:
                unit_match: Optional[Match] \
                    = self._program_unit_pattern.match(line)
                if unit_match:
                    unit_type: str = unit_match.group(1).lower()
                    unit_name: str = unit_match.group(2).lower()
                    logger.debug('Found %s called "%s"', unit_type, unit_name)
                    self._state.add_fortran_program_unit(
                        unit_name, self._reader.filename)
                    scope.append((unit_type, unit_name))
                    continue
            use_match: Optional[Match] \
                = self._use_pattern.match(line)
            if use_match:
                use_name: str = use_match.group(3).lower()
                if use_name in self._intrinsic_modules:
                    logger.debug('Ignoring intrinsic module "%s"', use_name)
                else:
                    if len(scope) == 0:
                        use_message \
                            = '"use" statement found outside program unit'
                        raise TaskException(use_message)
                    logger.debug('Found usage of "%s"', use_name)
                    self._state.add_fortran_dependency(scope[0][1], use_name)
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

            proc_match: Optional[Match] \
                = self._procedure_pattern.match(line)
            if proc_match:
                proc_nature = proc_match.group(1).lower()
                proc_name = proc_match.group(2).lower()
                logger.debug('Found %s called "%s"', proc_nature, proc_name)
                # Note: We append a tuple so double brackets.
                scope.append((proc_nature, proc_name))
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
                        end_message = 'Expected end of {exp} "{name}" ' \
                                      'but found {found}'
                        end_values = {'exp': exp[0],
                                      'name': exp[1],
                                      'found': end_nature}
                        raise TaskException(
                            end_message.format(**end_values))
                if end_name is not None:
                    if end_name != exp[1]:
                        end_message = 'Expected end of {exp} "{name}" ' \
                                      'but found end of {found}'
                        end_values = {'exp': exp[0],
                                      'name': exp[1],
                                      'found': end_name}
                        raise TaskException(
                            end_message.format(**end_values))
        return []


class FortranPreProcessor(Command):

    @property
    def as_list(self) -> List[str]:
        base_command = ['cpp', '-traditional-cpp', '-P']
        file_args = [str(self._filename), str(self.output_filename)]
        return base_command + self._flags + file_args

    @property
    def output_filename(self) -> Path:
        return self._workspace / self._filename.with_suffix('.f90').name

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Working state which is either per-build or persistent between builds.
'''
import sqlite3
from pathlib import Path
from typing import List, Any


class WorkingStateException(Exception):
    pass


class WorkingState(object):
    '''
    Provides a semi-permanent store of working state.

    Backed by a database which may be deleted at any point. It should not be
    used for permanent storage of e.g. configuration.
    '''
    def __init__(self, working_directory: Path):
        self._working_directory = working_directory

        if not self._working_directory.exists():
            self._working_directory.mkdir(parents=True)

        self._connection = sqlite3.connect(str(working_directory / 'state.db'))
        self._connection.row_factory = sqlite3.Row

        # According to the Fortran spec, section 3.2.2 in
        # BS ISO/IEC 1539-1:2010, the maximum size of a name is 63 characters.
        # Choosing a length for filenames is much less clear cut. I have gone
        # for 1k.
        #
        self._connection.execute('''create table if not exists fortran_unit
                                    (id integer primary key,
                                     unit character(63) not null,
                                     filename character(1024) not null)''')
        self._connection.execute(
            'create index if not exists idx_fortran_program_unit '
            'on fortran_unit(unit)')
        self._connection.execute(
            'create index if not exists idx_fortran_filename '
            'on fortran_unit(filename)')
        self._connection.commit()

    def __del__(self):
        self._connection.close()

    def add_fortran_program_unit(self, name: str, in_file: Path) -> None:
        '''
        Creates a record of a new program unit and the file it is found in.

        Note that the filename is absolute meaning that if you rename or move
        the source directory nothing will match up.

        :param name: Program unit name.
        :param in_file: Filename of source containing program unit.
        '''
        self._connection.execute(
            '''insert into fortran_unit (unit, filename) 
               values (:unit, :filename)''',
            {'unit': name, 'filename': str(in_file)})
        self._connection.commit()

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
        cursor: sqlite3.Cursor = self._connection.execute(
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
        cursor: sqlite3.Cursor = self._connection.execute(
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

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


class WorkingStateException(Exception):
    pass


class FileInfo(object):
    def __init__(self, filename: Path, adler32: int):
        self.filename = filename
        self.adler32 = adler32

    def __eq__(self, other):
        return (str(other.filename) == str(self.filename)) \
               and (other.adler32 == self.adler32)


class StateDatabase(object):
    '''
    Provides a semi-permanent store of working state.

    Backed by a database which may be deleted at any point. It should not be
    used for permanent storage of e.g. configuration.
    '''
    # The Posix standard specifies a value PATH_MAX but requires only that it
    # be greater than 256. Obviously this is too little for modern systems.
    # By way of example, Linux systems often define this value to be 4k.
    #
    # Given that we will often be working with Linux systems I have followed
    # suite.
    #
    _PATH_LENGTH = 1024 * 4

    def __init__(self, working_directory: Path):
        self._working_directory: Path = working_directory

        if not self._working_directory.exists():
            self._working_directory.mkdir(parents=True)

        self.connection: sqlite3.Connection \
            = sqlite3.connect(str(working_directory / 'state.db'))
        self.connection.row_factory = sqlite3.Row

        self.connection.execute(
            '''create table if not exists file_info (
                 id integer primary key,
                 filename character({filename}) not null,
                 adler32 integer not null
               )'''.format(filename=self._PATH_LENGTH)
        )
        self.connection.execute(
            'create index if not exists idx_file_info_adler32 '
            'on file_info(adler32)')
        self.connection.commit()

    def __del__(self):
        self.connection.close()

    def add_file_info(self, filename: Path, adler32: int) -> None:
        self.connection.execute(
            'delete from file_info where filename=:filename',
            {'filename': str(filename)})
        self.connection.execute(
            '''insert into file_info (filename, adler32)
            values (:filename, :adler32)''',
            {'filename': str(filename), 'adler32': adler32})
        self.connection.commit()

    def get_file_info(self, filename: Path) -> FileInfo:
        cursor: sqlite3.Cursor = self.connection.execute(
            '''select filename, adler32 from file_info
            where filename=:filename''',
            {'filename': str(filename)})
        row: sqlite3.Row = cursor.fetchone()
        if row is None:
            raise WorkingStateException('File information not found for: '
                                        + str(filename))
        return FileInfo(row['filename'], row['adler32'])

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Working state which is either per-build or persistent between builds.
'''
from abc import ABC, abstractmethod
from pathlib import Path
import sqlite3
from typing import Dict, Iterator, Optional, Sequence, Union


class WorkingStateException(Exception):
    pass


class FileInfo(object):
    def __init__(self, filename: Path, adler32: int):
        self.filename = filename
        self.adler32 = adler32

    def __eq__(self, other):
        if not isinstance(other, FileInfo):
            raise ValueError('Cannot compare FileInfo with none FileInfo')
        return (str(other.filename) == str(self.filename)) \
            and (other.adler32 == self.adler32)


class DatabaseRows(Iterator[Dict[str, str]]):
    def __init__(self, cursor: Optional[sqlite3.Cursor]):
        self._cursor = cursor

    def __next__(self) -> Dict[str, str]:
        if self._cursor is None:
            raise StopIteration()
        row = self._cursor.fetchone()
        if row is None:
            raise StopIteration()
        else:
            return row


class StateDatabase(ABC):
    @abstractmethod
    def execute(self, query: Union[Sequence[str], str],
                inserts: Dict[str, str]) -> DatabaseRows:
        raise NotImplementedError('Abstract methods must be implemented.')


class DatabaseDecorator(StateDatabase):
    def __init__(self, database: StateDatabase):
        self._database: StateDatabase = database

    def execute(self, query: Union[Sequence[str], str],
                inserts: Dict[str, str]) -> DatabaseRows:
        return self._database.execute(query, inserts)


class FileInfoDatabase(DatabaseDecorator):
    # The Posix standard specifies a value PATH_MAX but requires only that it
    # be greater than 256. Obviously this is too little for modern systems.
    # By way of example, Linux systems often define this value to be 4k.
    #
    # Given that we will often be working with Linux systems I have followed
    # suit.
    #
    PATH_LENGTH = 1024 * 4

    def __init__(self, database: StateDatabase):
        super().__init__(database)

        queries = ['''create table if not exists file_info (
                          id integer primary key,
                          filename character({filename_length}) not null,
                          adler32 integer not null
                          )'''.format(filename_length=self.PATH_LENGTH),
                   '''create index if not exists idx_file_info_adler32
                          on file_info(adler32)''']
        self.execute(queries, {})

    def __iter__(self) -> Iterator[FileInfo]:
        query = ['select * from file_info order by filename']
        rows: DatabaseRows = self.execute(query, {})
        for row in rows:
            yield FileInfo(Path(row['filename']), int(row['adler32']))

    def add_file_info(self, filename: Path, adler32: int) -> None:
        queries = ['delete from file_info where filename=:filename',
                   '''insert into file_info (filename, adler32)
                         values (:filename, :adler32)''']
        self.execute(queries,
                     {'filename': str(filename),
                      'adler32': str(adler32)})


class SqliteStateDatabase(StateDatabase):
    '''
    Provides a semi-permanent store of working state.

    Backed by a database which may be deleted at any point. It should not be
    used for permanent storage of e.g. configuration.
    '''
    def __init__(self, working_directory: Path):
        self._working_directory: Path = working_directory
        self._connection: Optional[sqlite3.Connection] = None

    def __del__(self):
        if self._connection is not None:
            self._connection.close()

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection \
                = sqlite3.connect(str(self._working_directory / 'state.db'))
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def execute(self, query: Union[Sequence[str], str],
                inserts: Dict[str, str]) -> DatabaseRows:
        connection = self._get_connection()
        if isinstance(query, str):
            query_list: Sequence[str] = [query]
        else:
            query_list = query

        cursor = None
        for command in query_list:
            cursor = connection.execute(command, inserts)
        connection.commit()

        return DatabaseRows(cursor)

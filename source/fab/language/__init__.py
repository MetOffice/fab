# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Modules for handling different program languages appear in this package.
'''
from abc import ABC, abstractmethod

from fab.database import SqliteStateDatabase
from fab.reader import TextReader


class TransformException(Exception):
    pass


class Analyser(ABC):
    def __init__(self, database: SqliteStateDatabase):
        self._database = database

    @property
    def database(self):
        return self._database

    @abstractmethod
    def analyse(self, file: TextReader) -> None:
        raise NotImplementedError('Abstract methods must be implemented')

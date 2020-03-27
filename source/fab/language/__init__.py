# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Modules for handling different program languages appear in this package.
'''
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from fab.database import SqliteStateDatabase
from fab.reader import TextReader


class TaskException(Exception):
    pass


class Task(ABC):
    @abstractmethod
    def run(self):
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def prerequisites(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def products(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')


class Analyser(Task):
    def __init__(self, reader: TextReader, database: SqliteStateDatabase):
        self._database = database
        self._reader = reader

    @property
    def database(self):
        return self._database

    @property
    def prerequisites(self) -> List[Path]:
        return [Path(self._reader.filename)]

    @property
    def products(self) -> List[Path]:
        return []


class Command(ABC):
    stdout = False

    def __init__(self, workspace: Path, flags: List[str]):
        self._workspace = workspace
        self._flags = flags

    @property
    @abstractmethod
    def as_list(self) -> List[str]:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def output(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def input(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')


class SingleFileCommand(Command):
    def __init__(self, filename: Path, workspace: Path, flags: List[str]):
        super().__init__(workspace, flags)
        self._filename = filename

    @property
    def input(self) -> List[Path]:
        return [self._filename]


class CommandTask(Task):
    def __init__(self, command: Command):
        self._command = command

    def run(self):
        process = subprocess.run(self._command.as_list, check=True)
        if self._command.stdout:
            with open(self._command.output_filename, 'wb') as out_file:
                out_file.write(process.stdout)

    @property
    def prerequisites(self) -> List[Path]:
        return self._command.input

    @property
    def products(self) -> List[Path]:
        return self._command.output

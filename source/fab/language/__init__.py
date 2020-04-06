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

from fab.database import StateDatabase
from fab.reader import TextReader


class TaskException(Exception):
    pass


class Task(ABC):
    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def prerequisites(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    @abstractmethod
    def products(self) -> List[Path]:
        raise NotImplementedError('Abstract methods must be implemented')


class Analyser(Task, ABC):
    def __init__(self, reader: TextReader, database: StateDatabase):
        self._database = database
        self._reader = reader

    @property
    def database(self):
        return self._database

    @property
    def prerequisites(self) -> List[Path]:
        if isinstance(self._reader.filename, Path):
            return [self._reader.filename]
        else:
            return []

    @property
    def products(self) -> List[Path]:
        return []


class Command(ABC):
    def __init__(self, workspace: Path, flags: List[str], stdout=False):
        self._workspace = workspace
        self._flags = flags
        self._output_is_stdout = stdout

    @property
    def stdout(self) -> bool:
        return self._output_is_stdout

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


class SingleFileCommand(Command, ABC):
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
        if self._command.stdout:
            process = subprocess.run(self._command.as_list,
                                     check=True,
                                     stdout=subprocess.PIPE)
            with self._command.output[0].open('wb') as out_file:
                out_file.write(process.stdout)
        else:
            _ = subprocess.run(self._command.as_list, check=True)

    @property
    def prerequisites(self) -> List[Path]:
        return self._command.input

    @property
    def products(self) -> List[Path]:
        return self._command.output

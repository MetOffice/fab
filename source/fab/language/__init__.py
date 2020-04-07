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

from fab.database import StateDatabase, FileInfoDatabase
from fab.reader import TextReader, TextReaderAdler32


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
    def __init__(self, reader: TextReader):
        self._reader = reader

    @abstractmethod
    def run(self, database: StateDatabase = None) -> None:
        raise NotImplementedError('Abstract methods must be implemented')

    @property
    def prerequisites(self) -> List[Path]:
        if isinstance(self._reader.filename, Path):
            return [self._reader.filename]
        else:
            return []

    @property
    def products(self) -> List[Path]:
        return []


class HashCalculator(Task):
    def __init__(self, hasher: TextReaderAdler32):
        self._hasher = hasher

    def run(self, database: StateDatabase = None) -> None:
        for _ in self._hasher.line_by_line():
            pass  # Make sure we've read the whole file.
        if database is not None:
            file_info = FileInfoDatabase(database)
            file_info.add_file_info(Path(self._hasher.filename),
                                    self._hasher.hash)

    @property
    def prerequisites(self) -> List[Path]:
        if isinstance(self._hasher.filename, Path):
            return [self._hasher.filename]
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

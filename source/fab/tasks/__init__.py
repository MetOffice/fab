# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Base classes for defining the main task units run by Fab.
'''
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from fab.artifact import Artifact


class TaskException(Exception):
    pass


class Task(ABC):
    @abstractmethod
    def run(self, artifact: Artifact) -> List[Artifact]:
        raise NotImplementedError('Abstract methods must be implemented')


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

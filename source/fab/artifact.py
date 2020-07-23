##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from abc import ABC
from typing import Type, List


# Classes representing possible states of an Artifact
class State(ABC):
    pass


class New(State):
    pass


class Seen(State):
    pass


class Raw(State):
    pass


class Analysed(State):
    pass


class Compiled(State):
    pass


class Linked(State):
    pass


# Classes representing possible filetypes
class FileType(ABC):
    pass


class Unknown(FileType):
    pass


class FortranSource(FileType):
    pass


class BinaryObject(FileType):
    pass


class Executable(FileType):
    pass


class Artifact(object):
    def __init__(self,
                 location: Path,
                 filetype: Type[FileType],
                 state: Type[State]) -> None:

        self._location = location
        self._filetype = filetype
        self._state = state
        self._defines: List[str] = []
        self._depends_on: List[str] = []

    @property
    def location(self) -> Path:
        return self._location

    @property
    def filetype(self) -> Type[FileType]:
        return self._filetype

    @property
    def state(self) -> Type[State]:
        return self._state

    @property
    def defines(self) -> List[str]:
        return self._defines

    @property
    def depends_on(self) -> List[str]:
        return self._depends_on

    def add_dependency(self, dependency: str) -> None:
        self._depends_on.append(dependency)

    def add_definition(self, definition: str) -> None:
        self._defines.append(definition)

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from abc import ABC
from typing import Type


# Classes representing possible states of an Artifact
class State(ABC):
    pass


class Aware(State):
    pass


class Seen(State):
    pass


class Ready(State):
    pass


class Prepared(State):
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

    @property
    def location(self) -> Path:
        return self._location

    @property
    def filetype(self) -> Type[FileType]:
        return self._filetype

    @property
    def state(self) -> Type[State]:
        return self._state

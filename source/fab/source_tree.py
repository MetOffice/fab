##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Descend a directory tree or trees processing source files found along the way.
"""
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Callable, Type
from fab.artifact import Artifact, FileType, State


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path) -> None:
        raise NotImplementedError("Abstract method must be implemented")


class PathMap(object):
    def __init__(self,
                 pattern: str,
                 filetype: Type[FileType],
                 state: Type[State]):
        self._pattern = pattern
        self._filetype = filetype
        self._state = state

    def match(self, path: Path) -> bool:
        matched = False
        if re.match(self._pattern, str(path)):
            matched = True
        return matched


class SourceVisitor(TreeVisitor):
    def __init__(self,
                 path_maps: List[PathMap],
                 artifact_handler: Callable):
        self._path_maps = path_maps
        self._artifact_handler = artifact_handler

    def visit(self, candidate: Path) -> None:
        for pathmap in self._path_maps:
            if pathmap.match(candidate):
                artifact = Artifact(candidate,
                                    pathmap._filetype,
                                    pathmap._state)
                self._artifact_handler(artifact)


class TreeDescent(object):
    def __init__(self, root: Path):
        self._root = root

    def descend(self, visitor: TreeVisitor):
        to_visit = [self._root]
        while len(to_visit) > 0:
            candidate: Path = to_visit.pop()
            if candidate.is_dir():
                to_visit.extend(sorted(candidate.iterdir()))
                continue

            # At this point the object should be a file, directories having
            # been dealt with previously.
            #
            visitor.visit(candidate)

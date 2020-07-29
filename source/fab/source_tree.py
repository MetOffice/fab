##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Descend a directory tree or trees processing source files found along the way.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable
from fab.artifact import Artifact, Unknown, New


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path) -> None:
        raise NotImplementedError("Abstract method must be implemented")


class SourceVisitor(TreeVisitor):
    def __init__(self,
                 artifact_handler: Callable):
        self._artifact_handler = artifact_handler

    def visit(self, candidate: Path) -> None:
        artifact = Artifact(candidate,
                            Unknown,
                            New)
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

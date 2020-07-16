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
from typing import Mapping, List, Type, Callable, Tuple, Union
from fab.database import SqliteStateDatabase
from fab.tasks import \
    Task, \
    Analyser, \
    Command, \
    SingleFileCommand
from fab.tasks.common import \
    CommandTask
from fab.reader import TextReader, FileTextReader


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path) -> List[Path]:
        raise NotImplementedError("Abstract method must be implemented")


class PathMap(object):
    def __init__(self,
                 mapping: List[Tuple[str, Union[Type[Task], Type[Command]]]]):
        self._mapping = mapping

    def get_task(self, path: Path) -> Union[Type[Task], Type[Command], None]:
        task = None
        for pattern, classname in self._mapping:
            # Note we keep searching through the map
            # even after a match is found; this means that
            # later matches will override earlier ones
            if re.match(pattern, str(path)):
                task = classname
        return task


class SourceVisitor(TreeVisitor):
    def __init__(self,
                 path_map: PathMap,
                 command_flags_map: Mapping[Type[Command], List[str]],
                 state: SqliteStateDatabase,
                 workspace: Path,
                 task_handler: Callable):
        self._path_map = path_map
        self._command_flags_map = command_flags_map
        self._state = state
        self._workspace = workspace
        self._task_handler = task_handler

    def visit(self, candidate: Path) -> List[Path]:
        new_candidates: List[Path] = []

        task_class = self._path_map.get_task(candidate)
        if task_class is None:
            return new_candidates

        reader: TextReader = FileTextReader(candidate)

        if issubclass(task_class, Analyser):
            task: Task = task_class(reader, self._state)
        elif issubclass(task_class, SingleFileCommand):
            flags = self._command_flags_map.get(task_class, [])
            task = CommandTask(
                task_class(Path(reader.filename), self._workspace, flags))
        else:
            message = \
                f"Unhandled class '{task_class}' in extension map."
            raise TypeError(message)

        self._task_handler(task)

        new_candidates.extend(task.products)
        return new_candidates


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
            to_visit.extend(visitor.visit(candidate))

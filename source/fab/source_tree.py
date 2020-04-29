##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Descend a directory tree or trees processing source files found along the way.
'''
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Mapping, List, Union, Type, Callable

from fab.database import SqliteStateDatabase
from fab.tasks import \
    Task, \
    Analyser, \
    Command, \
    SingleFileCommand
from fab.tasks.common import \
    CommandTask, \
    HashCalculator
from fab.reader import TextReader, FileTextReader


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path) -> List[Path]:
        raise NotImplementedError('Abstract method must be implemented')


class ExtensionVisitor(TreeVisitor):
    def __init__(self,
                 extension_map: Mapping[str, Union[Type[Task], Type[Command]]],
                 command_flags_map: Mapping[Type[Command], List[str]],
                 state: SqliteStateDatabase,
                 workspace: Path,
                 task_handler: Callable):
        self._extension_map = extension_map
        self._command_flags_map = command_flags_map
        self._state = state
        self._workspace = workspace
        self._task_handler = task_handler

    def visit(self, candidate: Path) -> List[Path]:
        new_candidates: List[Path] = []
        try:
            task_class = self._extension_map[candidate.suffix]
            reader: TextReader = FileTextReader(candidate)

            if issubclass(task_class, Analyser):
                task: Task = task_class(reader, self._state)
            elif issubclass(task_class, SingleFileCommand):
                flags = self._command_flags_map.get(task_class, [])
                task = CommandTask(
                    task_class(Path(reader.filename), self._workspace, flags))
            else:
                message = \
                    f'Unhandled class "{task_class}" in extension map.'
                raise TypeError(message)

            self._task_handler(task)
            self._task_handler(HashCalculator(reader, self._state))

            new_candidates.extend(task.products)

        except KeyError:
            pass
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

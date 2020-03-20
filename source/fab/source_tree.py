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
from typing import Mapping, List, Union, Type

from fab.database import FileInfoDatabase, SqliteStateDatabase
from fab.language import Task, Analyser, CommandTask, Command
from fab.reader import TextReader, FileTextReader, TextReaderAdler32


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path) -> List[Path]:
        raise NotImplementedError('Abstract method must be implemented')


class ExtensionVisitor(TreeVisitor):
    def __init__(self,
                 extension_map: Mapping[str, Union[Type[Task], Type[Command]]],
                 command_flags_map: Mapping[Type[Command], List[str]],
                 state: SqliteStateDatabase, workspace: Path):
        self._extension_map = extension_map
        self._command_flags_map = command_flags_map
        self._state = state
        self._workspace = workspace

    def visit(self, candidate: Path) -> List[Path]:
        new_candidates: List[Path] = []
        try:
            task_class = self._extension_map[candidate.suffix]
            reader: TextReader = FileTextReader(candidate)
            hasher: TextReaderAdler32 = TextReaderAdler32(reader)

            if issubclass(task_class, Analyser):
                task: Task = task_class(hasher, self._state)
            elif issubclass(task_class, Command):
                flags = self._command_flags_map.get(task_class, [])
                task = CommandTask(
                    task_class(Path(hasher.filename), self._workspace, flags))
            else:
                message = 'Unhandled class "{cls}" in extension map.'
                raise TypeError(
                    message.format(cls=task_class))
            # TODO: Eventually add to the queue here rather than running
            new_candidates = task.run()
            for _ in hasher.line_by_line():
                pass  # Make sure we've read the whole file.
            file_info = FileInfoDatabase(self._state)
            file_info.add_file_info(candidate, hasher.hash)
        except KeyError:
            pass
        return new_candidates


class TreeDescent(object):
    def __init__(self, root: Path):
        self._root = root

    def descend(self, visitor: TreeVisitor):
        addresses = [self._root]
        while len(addresses) > 0:
            candidate: Path = addresses.pop()
            if candidate.is_dir():
                addresses.extend(sorted(candidate.iterdir()))
                continue

            # At this point the object should be a file, directories having
            # been dealt with previously.
            #
            addresses.extend(visitor.visit(candidate))

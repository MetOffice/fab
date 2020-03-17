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
from typing import Mapping, List

from fab.database import FileInfoDatabase
from fab.language import Task, Analyser, CommandTask, Command
from fab.reader import TextReader, FileTextReader, TextReaderAdler32


class TreeVisitor(ABC):
    @abstractmethod
    def visit(self, candidate: Path):
        raise NotImplementedError('Abstract method must be implemented')


class ExtensionVisitor(TreeVisitor):
    def __init__(self, extension_map: Mapping[str, Task],
		 state: StateDatabase, workspace: Path):
        self._extension_map = extension_map
        self._state = state
        self._workspace = workspace

    def visit(self, candidate: Path):
        try:
            transform_class = self._extension_map[candidate.suffix]
            reader: TextReader = FileTextReader(candidate)
            hasher: TextReaderAdler32 = TextReaderAdler32(reader)

            if isinstance(transform, Analyser):
                transform = transform_class(candidate, self._state)
            elif isinstance(transform, Command):
                transform = CommandTask(transform_class(candidate, self._workspace))
	        # TODO: Eventually add to the queue here rather than running
            new_candidates: List[Path] = transform.run()
            for _ in hasher.line_by_line():
                pass  # Make sure we've read the whole file.
            file_info = FileInfoDatabase(analyser.database)
            file_info.add_file_info(candidate, hasher.hash)
            for new_candidate in new_candidates:
                self.visit(new_candidate)
        except KeyError:
            pass


class TreeDescent(object):
    def __init__(self, root: Path):
        self._root = root

    def descend(self, visitor: TreeVisitor):
        visit = [self._root]
        while len(visit) > 0:
            candidate: Path = visit.pop()
            if candidate.is_dir():
                visit.extend(sorted(candidate.iterdir()))
                continue

            # At this point the object should be a file, directories having
            # been dealt with previously.
            #
            visitor.visit(candidate)

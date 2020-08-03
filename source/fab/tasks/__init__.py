# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Base classes for defining the main task units run by Fab.
'''
import re
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Optional, Match

from fab.artifact import Artifact, HeadersAnalysed
from fab.reader import FileTextReader


class TaskException(Exception):
    pass


class Task(ABC):
    @abstractmethod
    def run(self, artifacts: List[Artifact]) -> List[Artifact]:
        raise NotImplementedError('Abstract methods must be implemented')


class HeaderAnalyser(Task):
    _include_re = r'^\s*#include\s+(\S+)'
    _include_pattern = re.compile(_include_re)

    def __init__(self, workspace: Path):
        self._workspace = workspace

    def run(self, artifacts: List[Artifact]) -> List[Artifact]:
        if len(artifacts) == 1:
            artifact = artifacts[0]
        else:
            msg = ('Header Analyser expects only one Artifact, '
                   f'but was given {len(artifacts)}')
            raise TaskException(msg)

        new_artifact = Artifact(artifact.location,
                                artifact.filetype,
                                HeadersAnalysed)

        reader = FileTextReader(artifact.location)
        for line in reader.line_by_line():
            include_match: Optional[Match] \
                = self._include_pattern.match(line)
            if include_match:
                include: str = include_match.group(1)
                if include.startswith(('"', "'")):
                    include = include.strip('"').strip("'")
                    new_artifact.add_dependency(
                        Path(self._workspace / include))

        return [new_artifact]

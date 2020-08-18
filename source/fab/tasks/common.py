# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution

import re
import subprocess
from typing import List, Optional, Match
from pathlib import Path

from fab.artifact import \
    Artifact, \
    Executable, \
    HeadersAnalysed, \
    Linked
from fab.tasks import Task, TaskException
from fab.reader import FileTextReader


class Linker(Task):
    def __init__(self,
                 linker: str,
                 flags: List[str],
                 workspace: Path,
                 output_filename: str):
        self._linker = linker
        self._flags = flags
        self._workspace = workspace
        self._output_filename = output_filename

    def run(self, artifacts: List[Artifact]) -> List[Artifact]:

        if len(artifacts) < 1:
            msg = ('Linker expects at least one Artifact, '
                   f'but was given {len(artifacts)}')
            raise TaskException(msg)

        command = [self._linker]

        output_file = self._workspace / self._output_filename

        command.extend(['-o', str(output_file)])
        for artifact in artifacts:
            command.append(str(artifact.location))

        command.extend(self._flags)

        subprocess.run(command, check=True)

        return [Artifact(output_file,
                         Executable,
                         Linked)]


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

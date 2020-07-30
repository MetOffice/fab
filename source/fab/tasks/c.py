# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
"""
C language handling classes.
"""
import subprocess
import re
from typing import List, Iterator, Pattern, Optional, Match
from pathlib import Path

from fab.tasks import Task, TaskException
from fab.artifact import Artifact, Raw, Modified
from fab.reader import \
    TextReader, \
    FileTextReader, \
    TextReaderDecorator


class CTextReaderPragmas(TextReaderDecorator):
    """
    Reads a C source file but when encountering an #include
    preprocessor directive injects a special Fab-specific
    #pragma which can be picked up later by the Analyser
    after the preprocessing
    """
    def __init__(self, source: TextReader):
        super().__init__(source)
        self._line_buffer = ''

    _include_re: str = r'^\s*#include\s+(\S+)'
    _include_pattern: Pattern = re.compile(_include_re)

    def line_by_line(self) -> Iterator[str]:
        for line in self._source.line_by_line():
            include_match: Optional[Match] \
                = self._include_pattern.match(line)
            if include_match:
                # For valid C the first character of the matched
                # part of the group will indicate whether this is
                # a system library include or a user include
                include: str = include_match.group(1)
                # TODO: Is this sufficient?  Or do the pragmas
                #       need to include identifying info
                #       e.g. the name of the original include?
                if include.startswith('<'):
                    yield '#pragma FAB SysIncludeStart\n'
                    yield line
                    yield '#pragma FAB SysIncludeEnd\n'
                elif include.startswith(('"', "'")):
                    yield '#pragma FAB UsrIncludeStart\n'
                    yield line
                    yield '#pragma FAB UsrIncludeEnd\n'
                else:
                    msg = 'Found badly formatted #include'
                    raise TaskException(msg)
            else:
                yield line


class CPragmaInjector(Task):
    def __init__(self, workspace: Path):
        self._workspace = workspace

    def run(self, artifacts: List[Artifact]) -> List[Artifact]:

        if len(artifacts) == 1:
            artifact = artifacts[0]
        else:
            msg = ('C Pragma Injector expects only one Artifact, '
                   f'but was given {len(artifacts)}')
            raise TaskException(msg)

        injector = CTextReaderPragmas(
            FileTextReader(artifact.location))

        output_file = self._workspace / artifact.location.name

        out_lines = [line for line in injector.line_by_line()]

        with output_file.open('w') as out_file:
            for line in out_lines:
                out_file.write(line)

        return [Artifact(output_file,
                         artifact.filetype,
                         Modified)]


class CPreProcessor(Task):
    def __init__(self,
                 preprocessor: str,
                 flags: List[str],
                 workspace: Path):
        self._preprocessor = preprocessor
        self._flags = flags
        self._workspace = workspace

    def run(self, artifacts: List[Artifact]) -> List[Artifact]:

        if len(artifacts) == 1:
            artifact = artifacts[0]
        else:
            msg = ('C Preprocessor expects only one Artifact, '
                   f'but was given {len(artifacts)}')
            raise TaskException(msg)

        command = [self._preprocessor]
        command.extend(self._flags)
        command.append(str(artifact.location))

        # Use temporary output name (in case the given tool
        # can't operate in-place)
        output_file = (self._workspace /
                       artifact.location.with_suffix('.fabcpp').name)

        command.append(str(output_file))
        subprocess.run(command, check=True)

        # Overwrite actual output file
        final_output = (self._workspace /
                        artifact.location.name)
        command = ["mv", str(output_file), str(final_output)]
        subprocess.run(command, check=True)

        return [Artifact(final_output,
                         artifact.filetype,
                         Raw)]

# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Tasks which are not language specific.
'''
import subprocess
from typing import List
from pathlib import Path
from zlib import adler32

from fab.tasks import Task, Command
from fab.database import StateDatabase, FileInfoDatabase
from fab.reader import FileTextReader
from fab.artifact import Artifact


class HashCalculator(Task):
    def __init__(self, database: StateDatabase) -> None:
        self._database = database

    def run(self, artifact: Artifact) -> List[Artifact]:
        reader = FileTextReader(artifact.location)
        fhash = 1
        for line in reader.line_by_line():
            fhash = adler32(bytes(line, encoding='utf-8'), fhash)
        file_info = FileInfoDatabase(self._database)
        file_info.add_file_info(artifact.location, fhash)
        return []


class CommandTask(Task):
    def __init__(self, command: Command):
        self._command = command

    def run(self):
        if self._command.stdout:
            process = subprocess.run(self._command.as_list,
                                     check=True,
                                     stdout=subprocess.PIPE)
            with self._command.output[0].open('wb') as out_file:
                out_file.write(process.stdout)
        else:
            _ = subprocess.run(self._command.as_list, check=True)

    @property
    def prerequisites(self) -> List[Path]:
        return self._command.input

    @property
    def products(self) -> List[Path]:
        return self._command.output

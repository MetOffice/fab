# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Tasks which are not language specific.
'''
from typing import List
from zlib import adler32

from fab.tasks import Task, TaskException
from fab.database import StateDatabase, FileInfoDatabase
from fab.reader import FileTextReader
from fab.artifact import Artifact


class HashCalculator(Task):
    def __init__(self, database: StateDatabase) -> None:
        self._database = database

    def run(self, artifacts: List[Artifact]) -> List[Artifact]:

        if len(artifacts) == 1:
            artifact = artifacts[0]
        else:
            msg = ('Hash Calculator expects only one Artifact, '
                   f'but was given {len(artifacts)}')

            raise TaskException(msg)

        reader = FileTextReader(artifact.location)
        fhash = 1
        for line in reader.line_by_line():
            fhash = adler32(bytes(line, encoding='utf-8'), fhash)
        file_info = FileInfoDatabase(self._database)
        file_info.add_file_info(artifact.location, fhash)
        return []

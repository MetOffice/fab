##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Core of the database dump application.
"""

from pathlib import Path
import sys

from fab.database import FileInfoDatabase, SqliteStateDatabase
from fab.tasks.fortran import FortranWorkingState


class Dump(object):
    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._state = SqliteStateDatabase(workspace)

    def run(self, stream=sys.stdout):
        file_view = FileInfoDatabase(self._state)
        print("File View", file=stream)
        for file_info in file_view:
            print(f"  File   : {file_info.filename}", file=stream)
            # Where files are generated in the working directory
            # by third party tools, we cannot guarantee the hashes
            if file_info.filename.match(f'{self._workspace}/*'):
                print('    Hash : --hidden-- (generated file)')
            else:
                print(f"    Hash : {file_info.adler32}", file=stream)

        fortran_view = FortranWorkingState(self._state)
        print("Fortran View", file=stream)
        for info in fortran_view:
            print(f"  Program unit    : {info.unit.name}", file=stream)
            print(f"    Found in      : {info.unit.found_in}", file=stream)
            print(f"    Prerequisites : {', '.join(info.depends_on)}",
                  file=stream)

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Dict, Mapping, Type, Union

from fab.database import SqliteStateDatabase
from fab.language import Task, Command
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor
from fab.source_tree import TreeDescent, ExtensionVisitor, FileInfoDatabase


class Fab(object):
    _extension_map: Dict[str, Union[Task, Command]] = {
        '.f90': FortranAnalyser,
        '.F90': FortranPreProcessor,
    }

    def __init__(self, workspace: Path):
        self._state = SqliteStateDatabase(workspace)
        self._workspace = workspace

    def run(self, source: Path):
        visitor = ExtensionVisitor(self._extension_map, 
                                   self._state, 
                                   self._workspace)
        descender = TreeDescent(source)
        descender.descend(visitor)

        file_db = FileInfoDatabase(self._state)
        for file in file_db.get_all_filenames():
            info = file_db.get_file_info(file)
            print(info.filename)
            print(f'    hash: {info.adler32}')

        fortran_db = FortranWorkingState(self._state)
        for unit, files in fortran_db.iterate_program_units():
            print(unit)
            for filename in files:
                print('    found in: ' + str(filename))
                print('    depends on: ' + str(fortran_db.depends_on(unit)))

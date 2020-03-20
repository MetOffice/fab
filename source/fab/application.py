##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Dict, Type, Union, List

from fab.database import SqliteStateDatabase
from fab.language import Task, Command
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor
from fab.source_tree import TreeDescent, ExtensionVisitor, FileInfoDatabase


class Fab(object):
    _extension_map: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.f90': FortranAnalyser,
        '.F90': FortranPreProcessor,
    }
    _command_flags_map: Dict[Type[Command], List[str]] = {}

    def __init__(self, workspace: Path, fpp_flags: str):
        self._state = SqliteStateDatabase(workspace)
        self._workspace = workspace
        if fpp_flags != '':
            self._command_flags_map[FortranPreProcessor] = (
                fpp_flags.split()
            )

    def run(self, source: Path):
        visitor = ExtensionVisitor(self._extension_map,
                                   self._command_flags_map,
                                   self._state,
                                   self._workspace)
        descender = TreeDescent(source)
        descender.descend(visitor)

        file_db = FileInfoDatabase(self._state)
        for file in file_db.get_all_filenames():
            info = file_db.get_file_info(file)
            print(info.filename)
            # Where files are generated in the working directory
            # by third party tools, we cannot guarantee the hashes
            if str(info.filename).startswith(str(self._workspace)):
                print('    hash: --hidden-- (generated file)')
            else:
                print(f'    hash: {info.adler32}')

        fortran_db = FortranWorkingState(self._state)
        for unit, files in fortran_db.iterate_program_units():
            print(unit)
            for filename in files:
                print('    found in: ' + str(filename))
                print('    depends on: ' + str(fortran_db.depends_on(unit)))

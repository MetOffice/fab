##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from typing import Dict, Mapping, Type

from fab.database import SqliteStateDatabase
from fab.language import Analyser, PreProcessor
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor
from fab.source_tree import TreeDescent, ExtensionVisitor, FileInfoDatabase


class Fab(object):
    _analysers: Dict[str, Type[Analyser]] = {
        '.f90': FortranAnalyser
    }

    def __init__(self, workspace: Path):
        self._state = SqliteStateDatabase(workspace)
        self._analyser_map: Mapping[str, Analyser] \
            = {extension: analyser(self._state)
               for extension, analyser in self._analysers.items()}
        self._preprocessor_map: Dict[str, PreProcessor] = {
            ".F90": FortranPreProcessor("cpp", "", workspace)
        }

    def run(self, source: Path):
        visitor = ExtensionVisitor(self._analyser_map)
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

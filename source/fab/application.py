##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import sys
from typing import Dict, Mapping, Type

from fab.database import StateDatabase
from fab.language import Analyser
from fab.language.fortran import FortranAnalyser, FortranWorkingState
from fab.source_tree import TreeDescent, ExtensionVisitor


class Fab(object):
    _extensions: Dict[str, Type[Analyser]] = {
        '.F90': FortranAnalyser,
        '.f90': FortranAnalyser
    }

    def __init__(self, workspace: Path):
        self._state = StateDatabase(workspace)
        self._extension_map: Mapping[str, Analyser] \
            = {extension: analyser(self._state)
               for extension, analyser in self._extensions.items()}

    def run(self, source: Path):
        visitor = ExtensionVisitor(self._extension_map)
        descender = TreeDescent(source)
        descender.descend(visitor)

        db = FortranWorkingState(self._state)
        for unit, files in db.iterate_program_units():
            print(unit)
            for filename in files:
                print('    found in: ' + str(filename))
                print('    depends on: ' + str(db.depends_on(unit)))


class Dump(object):
    def __init__(self, workspace: Path):
        self._state = StateDatabase(workspace)

    def run(self, stream=sys.stdout):
        fortran_view = FortranWorkingState(self._state)
        print("Fortran View", file=stream)
        for program_unit, found_in in fortran_view.iterate_program_units():
            filenames = (str(path) for path in found_in)
            print(f"  Program unit    : {program_unit}", file=stream)
            print(f"    Found in      : {', '.join(filenames)}", file=stream)
            prerequisites = fortran_view.depends_on(program_unit)
            print(f"    Prerequisites : {', '.join(prerequisites)}",
                  file=stream)

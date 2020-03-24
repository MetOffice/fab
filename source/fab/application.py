##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import sys
from typing import Dict, List, Type, Union

from fab.database import SqliteStateDatabase
from fab.language import \
    Task, \
    Command, \
    CommandTask, \
    SingleFileCommand, \
    Linker
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranCompiler
from fab.source_tree import TreeDescent, ExtensionVisitor, FileInfoDatabase


class Fab(object):
    _extension_map: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.f90': FortranAnalyser,
        '.F90': FortranPreProcessor,
    }
    _compiler_map: Dict[str, Type[SingleFileCommand]] = {
        '.f90': FortranCompiler,
    }

    def __init__(self, workspace: Path, fpp_flags: str):
        self._state = SqliteStateDatabase(workspace)
        self._workspace = workspace

        self._command_flags_map: Dict[Type[Command], List[str]] = {}
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
            if info.filename.match(f'{self._workspace}/*'):
                print('    hash: --hidden-- (generated file)')
            else:
                print(f'    hash: {info.adler32}')

        fortran_db = FortranWorkingState(self._state)
        for unit, files in fortran_db.iterate_program_units():
            print(unit)
            for filename in files:
                print('    found in: ' + str(filename))
                print('    depends on: ' + str(fortran_db.depends_on(unit)))

        # TODO: get name of top level unit here from the command line
        unit_to_process = ["some_program"]

        # Initialise linker
        # TODO: again, the linker needs flags passing, and
        #       an executable name
        executable = Path(self._workspace / "fab_exec.exe")
        link_command = Linker(self._workspace, [], executable)

        processed_units = []

        while unit_to_process:
            # Pop pending items from start of the list
            unit = unit_to_process.pop(0)
            dependencies = fortran_db.depends_on(unit)

            # First prune any dependencies that have already
            # been compiled
            for dependee in list(dependencies):
                if dependee in processed_units:
                    dependencies.remove(dependee)

            # Add unhandled dependencies to end of list
            if dependencies:
                for dependee in dependencies:
                    if dependee not in unit_to_process:
                        unit_to_process.append(dependee)
                # Re-add this unit after them for reconsideration
                # note that we *do not* do this in the else branch
                unit_to_process.append(unit)
            else:
                filenames = fortran_db.filenames_from_program_unit(unit)
                # TODO: should this be done by the database?
                #       preprocessing should ensure no duplicate units
                if len(filenames) == 1:
                    filename = filenames[0]
                else:
                    raise ValueError("Duplicate program unit found")

                compiler_class = self._compiler_map[filename.suffix]
                # TODO: Like the preprocessor need to pass any flags
                #       through to this point eventually
                compiler = CommandTask(
                    compiler_class(filename, self._workspace, []))
                # Add the object files to the linker
                link_command.add_object(compiler.run()[0])
                # And indicate that this unit has been processed
                processed_units.append(unit)

        # Hopefully by this point the list is exhausted and
        # everything has been compiled, and the linker is primed
        linker = CommandTask(link_command)
        linker.run()


class Dump(object):
    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._state = SqliteStateDatabase(workspace)

    def run(self, stream=sys.stdout):
        file_view = FileInfoDatabase(self._state)
        print("File View", file=stream)
        for filename in file_view.get_all_filenames():
            file_info = file_view.get_file_info(filename)
            print(f"  File   : {file_info.filename}", file=stream)
            # Where files are generated in the working directory
            # by third party tools, we cannot guarantee the hashes
            if file_info.filename.match(f'{self._workspace}/*'):
                print('    Hash : --hidden-- (generated file)')
            else:
                print(f"    Hash : {file_info.adler32}", file=stream)

        fortran_view = FortranWorkingState(self._state)
        print("Fortran View", file=stream)
        for program_unit, found_in in fortran_view.iterate_program_units():
            filenames = (str(path) for path in found_in)
            print(f"  Program unit    : {program_unit}", file=stream)
            print(f"    Found in      : {', '.join(filenames)}", file=stream)
            prerequisites = fortran_view.depends_on(program_unit)
            print(f"    Prerequisites : {', '.join(prerequisites)}",
                  file=stream)

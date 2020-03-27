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
    CommandTask
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranCompiler, \
    FortranLinker
from fab.source_tree import TreeDescent, ExtensionVisitor, FileInfoDatabase


class Fab(object):
    _extension_map: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.f90': FortranAnalyser,
        '.F90': FortranPreProcessor,
    }
    _compiler_map: Dict[str, Type[Command]] = {
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

        # TODO: This is where the threads first separate
        #       master thread stays to manage queue workers.
        #       One thread performs descent below.
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
        link_command = FortranLinker(self._workspace, [], executable)

        processed_units = []

        while unit_to_process:
            # Pop pending items from start of the list
            unit = unit_to_process.pop(0)
            if unit in processed_units:
                continue

            dependencies = fortran_db.depends_on(unit)
            unit_to_process.extend(dependencies)

            filenames = fortran_db.filenames_from_program_unit(unit)
            # TODO: should this be done by the database?
            #       preprocessing should ensure no duplicate units
            if len(filenames) == 1:
                filename = filenames[0]
            else:
                raise ValueError("Duplicate program unit found")

            # Construct names of any expected module files to
            # pass to the compiler constructor
            mod_files = [Path(self._workspace /
                              dependee).with_suffix('.mod')
                         for dependee in dependencies]

            compiler_class = self._compiler_map[filename.suffix]
            # TODO: Like the preprocessor need to pass any flags
            #       through to this point eventually
            if issubclass(compiler_class, FortranCompiler):
                compiler = CommandTask(
                    compiler_class(
                        filename,
                        self._workspace,
                        [],
                        mod_files))
            else:
                message = 'Unhandled class "{cls}" in compiler map.'
                raise TypeError(
                    message.format(cls=compiler_class))

            # TODO: At this point we would add this to the queue
            #       rather than running it here.  Noting that
            #       the queue worked can extract the prerequisites
            #       from the Task object.  For now we are going
            #       to have to fake that logic here:
            if all([prereq.exists() for prereq in compiler.prerequisites]):
                compiler.run()
                # Indicate that this unit has been processed, so we
                # don't do it again if we encounter it a second time
                processed_units.append(unit)
                # Add the object files to the linker
                # TODO: For right now products is a list, though the
                #       compiler only ever produces a single entry;
                #       maybe add_object should accept Union[Path, List[Path]]?
                link_command.add_object(compiler.products[0])
            else:
                # Re-add this to the set of units to process
                # (at the end, so that it is reconsidered after
                # other tasks have resolved)
                unit_to_process.append(unit)

        # Hopefully by this point the list is exhausted and
        # everything has been compiled, and the linker is primed
        linker = CommandTask(link_command)
        # TODO: Like the others, this would go on the queue
        #       now that it has knowledge of all its prerequisite
        #       object files
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

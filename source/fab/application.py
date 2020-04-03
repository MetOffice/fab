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
from fab.queue import QueueManager


class Fab(object):
    _extension_map: Dict[str, Union[Type[Task], Type[Command]]] = {
        '.f90': FortranAnalyser,
        '.F90': FortranPreProcessor,
    }
    _compiler_map: Dict[str, Type[Command]] = {
        '.f90': FortranCompiler,
    }

    def __init__(self,
                 workspace: Path,
                 target: str,
                 exec_name: str,
                 fpp_flags: str,
                 fc_flags: str,
                 ld_flags: str,
                 n_procs: int):

        self._state = SqliteStateDatabase(workspace)
        self._workspace = workspace
        self._target = target
        self._exec_name = exec_name

        self._command_flags_map: Dict[Type[Command], List[str]] = {}
        if fpp_flags != '':
            self._command_flags_map[FortranPreProcessor] = (
                fpp_flags.split()
            )
        if fc_flags != '':
            self._command_flags_map[FortranCompiler] = (
                fc_flags.split()
            )
        if ld_flags != '':
            self._command_flags_map[FortranLinker] = (
                ld_flags.split()
            )
        if n_procs is None:
            n_procs = 2
        self._queue = QueueManager(n_procs)

    def run(self, source: Path):

        self._queue.run()

        # TODO: This is where the threads first separate
        #       master thread stays to manage queue workers.
        #       One thread performs descent below.
        visitor = ExtensionVisitor(self._extension_map,
                                   self._command_flags_map,
                                   self._state,
                                   self._workspace,
                                   self._queue)
        descender = TreeDescent(source)
        descender.descend(visitor)

        self._queue.check_queue_done()

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

        # Start with the top level program unit
        unit_to_process = [self._target]

        # Initialise linker
        if self._exec_name != "":
            executable = Path(self._workspace) / self._exec_name
        else:
            executable = Path(self._workspace / self._target)

        flags = self._command_flags_map.get(FortranLinker, [])
        link_command = FortranLinker(self._workspace, flags, executable)

        processed_units = []

        while unit_to_process:
            # Pop pending items from start of the list
            unit = unit_to_process.pop(0)
            if unit in processed_units:
                continue

            dependencies = fortran_db.depends_on(unit)
            unit_to_process.extend(dependencies)

            filenames = fortran_db.filenames_from_program_unit(unit)
            # TODO: For now we simply can't handle this returning
            #       multiple names; later we may be able to deal with
            #       this via extra information in the configuration
            if len(filenames) == 1:
                filename = filenames[0]
            else:
                raise ValueError("Duplicate program unit found")

            # Construct names of any expected module files to
            # pass to the compiler constructor
            # TODO: Note that this currently assumes all of the
            #       dependencies we found were modules; we are
            #       going to need a way to get that information
            #       from the database
            mod_files = [Path(self._workspace /
                              dependee).with_suffix('.mod')
                         for dependee in dependencies]

            # TODO: It would also be good here to be able to
            #       generate a list of mod files which we
            #       expect to be *produced* by the compile
            #       and pass this to the constructor for
            #       inclusion in the task's "products"
            compiler_class = self._compiler_map[filename.suffix]

            if issubclass(compiler_class, FortranCompiler):
                flags = self._command_flags_map.get(compiler_class, [])
                compiler = CommandTask(
                    compiler_class(
                        filename,
                        self._workspace,
                        flags,
                        mod_files))
            else:
                message = \
                    f'Unhandled class "{compiler_class}" in compiler map.'
                raise TypeError(message)

            self._queue.add_to_queue(compiler)
            # Indicate that this unit has been processed, so we
            # don't do it again if we encounter it a second time
            processed_units.append(unit)
            # Add the object files to the linker
            # TODO: For right now products is a list, though the
            #       compiler only ever produces a single entry;
            #       maybe add_object should accept Union[Path, List[Path]]?
            link_command.add_object(compiler.products[0])

        # Hopefully by this point the list is exhausted and
        # everything has been compiled, and the linker is primed
        linker = CommandTask(link_command)
        self._queue.add_to_queue(linker)
        self._queue.check_queue_done()
        self._queue.shutdown()


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

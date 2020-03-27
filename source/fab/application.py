##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from collections import defaultdict
from pathlib import Path
import sys
import tkinter as tk
import tkinter.ttk as ttk
from typing import Dict, List, Type, Union

from fab import FabException
from fab.database import SqliteStateDatabase
from fab.language import \
    Task, \
    Command, \
    CommandTask
from fab.language.fortran import \
    FortranAnalyser, \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranUnitID, \
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

        self._workspace = workspace
        if not workspace.exists():
            workspace.mkdir(parents=True)

        self._state = SqliteStateDatabase(workspace)
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
        self._queue = QueueManager(n_procs - 1)

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
        for file_info in file_db:
            print(file_info.filename)
            # Where files are generated in the working directory
            # by third party tools, we cannot guarantee the hashes
            if file_info.filename.match(f'{self._workspace}/*'):
                print('    hash: --hidden-- (generated file)')
            else:
                print(f'    hash: {file_info.adler32}')

        fortran_db = FortranWorkingState(self._state)
        for fortran_info in fortran_db:
            print(fortran_info.unit.name)
            print('    found in: ' + str(fortran_info.unit.found_in))
            print('    depends on: ' + str(fortran_info.depends_on))

        # Start with the top level program unit
        target_info = fortran_db.get_program_unit(self._target)
        if len(target_info) > 1:
            alt_filenames = [str(info.unit.found_in) for info in target_info]
            message = f"Ambiguous top-level program unit '{self._target}', " \
                f"found in: {', '.join(alt_filenames)}"
            raise FabException(message)
        unit_to_process: List[FortranUnitID] = [target_info[0].unit]

        # Initialise linker
        if self._exec_name != "":
            executable = Path(self._workspace) / self._exec_name
        else:
            executable = Path(self._workspace / self._target)

        flags = self._command_flags_map.get(FortranLinker, [])
        link_command = FortranLinker(self._workspace, flags, executable)

        processed_units: List[FortranUnitID] = []

        while unit_to_process:
            # Pop pending items from start of the list
            unit = unit_to_process.pop(0)
            if unit in processed_units:
                continue

            dependencies: Dict[str, List[FortranUnitID]] = defaultdict(list)
            for prereq in fortran_db.depends_on(unit):
                dependencies[prereq.name].append(prereq)
            for name, alt_prereqs in dependencies.items():
                if len(alt_prereqs) > 1:
                    filenames = [str(path) for path in alt_prereqs]
                    message = f"Ambiguous prerequiste '{name}' " \
                        f"found in: {', '.join(filenames)}"
                    raise FabException(message)
                unit_to_process.append(alt_prereqs[0])

            # Construct names of any expected module files to
            # pass to the compiler constructor
            # TODO: Note that this currently assumes all of the
            #       dependencies we found were modules; we are
            #       going to need a way to get that information
            #       from the database
            mod_files = [Path(self._workspace /
                              dependee).with_suffix('.mod')
                         for dependee in dependencies.keys()]

            # TODO: It would also be good here to be able to
            #       generate a list of mod files which we
            #       expect to be *produced* by the compile
            #       and pass this to the constructor for
            #       inclusion in the task's "products"
            compiler_class = self._compiler_map[unit.found_in.suffix]

            if issubclass(compiler_class, FortranCompiler):
                flags = self._command_flags_map.get(compiler_class, [])
                compiler = CommandTask(
                    compiler_class(
                        unit.found_in,
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


class FileInfoFrame(tk.Frame):
    def __init__(self, parent: tk.Widget, file_db: FileInfoDatabase):
        super().__init__(parent)
        self.pack(side=tk.LEFT, fill=tk.Y)

        self._file_db = file_db

        tk.Label(self, text='Hash :').grid(row=0, column=0, sticky=tk.E)
        self._hash_field = tk.Entry(self, width=10)
        self._hash_field.grid(row=0, column=1, sticky=tk.W)

    def change_file(self, filename: Path):
        info = self._file_db.get_file_info(filename)
        self._hash_field.delete(0, tk.END)
        self._hash_field.insert(0, info.adler32)


class UnitInfoFrame(tk.Frame):
    def __init__(self, parent: tk.Widget, fortran_db: FortranWorkingState):
        super().__init__(parent)
        self.pack(side=tk.LEFT, fill=tk.Y)

        self._fortran_db = fortran_db

        tk.Label(self, text='Found in').grid(row=0, column=0)
        self._found_in_field = tk.Listbox(self, selectmode=tk.BROWSE, width=40)
        self._found_in_field.grid(row=1, column=0)

        tk.Label(self, text='Prerequisites').grid(row=0, column=1)
        self._prerequisite_field = tk.Listbox(self, selectmode=tk.BROWSE)
        self._prerequisite_field.grid(row=1, column=1)

    def change_unit(self, name: str):
        info_list = self._fortran_db.get_program_unit(name)
        self._found_in_field.delete(0, tk.END)
        for info in info_list:
            self._found_in_field.insert(tk.END, info.unit.found_in)
            # TODO: Clearly this is wrong, it concatenates all
            #       dependencies from every version of the module.
            self._prerequisite_field.delete(0, tk.END)
            for unit in info.depends_on:
                self._prerequisite_field.insert(tk.END, unit)


class Explorer(tk.Frame):
    def __init__(self, workspace: Path):
        self._state = SqliteStateDatabase(workspace)

        root = tk.Tk()
        root.title("Fab Database Explorer")
        super().__init__(root)
        self.pack()

        menu_bar = tk.Menu(root)

        app_menu = tk.Menu(menu_bar, tearoff=0)
        app_menu.add_command(label='Exit', command=root.quit)
        menu_bar.add_cascade(label='Application', menu=app_menu)

        root.config(menu=menu_bar)

        notebook = ttk.Notebook(root)
        notebook.pack(expand=1, fill='both')

        file_frame = ttk.Frame(notebook)
        notebook.add(file_frame, text="File view")

        def file_click(event):
            selection = file_list.get(file_list.curselection())
            file_details.change_file(Path(selection))

        file_db = FileInfoDatabase(self._state)
        file_list = tk.Listbox(file_frame, selectmode=tk.BROWSE, width=40)
        file_list.pack(side=tk.LEFT, fill=tk.BOTH)
        file_list.bind('<ButtonRelease-1>', file_click)
        for file_info in file_db:
            file_list.insert(tk.END, file_info.filename)
        file_details = FileInfoFrame(file_frame, file_db)

        fortran_frame = ttk.Frame(notebook)
        notebook.add(fortran_frame, text="Fortran view")

        def fortran_click(event):
            selection = unit_list.get(unit_list.curselection())
            unit_details.change_unit(selection)

        fortran_db = FortranWorkingState(self._state)
        unit_list = tk.Listbox(fortran_frame, selectmode=tk.BROWSE)
        unit_list.pack(side=tk.LEFT, fill=tk.BOTH)
        unit_list.bind('<ButtonRelease-1>', fortran_click)
        for unit_info in fortran_db:
            unit_list.insert(tk.END, unit_info.unit.name)
        unit_details = UnitInfoFrame(fortran_frame, fortran_db)

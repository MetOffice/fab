##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
GUI for the database explorer.
"""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk

from fab.database import FileInfoDatabase, StateDatabase
from fab.language.fortran import FortranWorkingState


class ExplorerWindow(tk.Frame):
    """
    Main window of the database explorer.
    """
    def __init__(self, state: StateDatabase):
        self._root = tk.Tk()
        self._root.title("Fab Database Explorer")
        super().__init__(self._root)
        self.pack()

        self._state = state

        self._menu_bar = MenuBar(self._root, self)

        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(expand=1, fill='both')

        file_frame = tk.Frame(self._notebook)
        self._notebook.add(file_frame, text="File view")

        file_db = FileInfoDatabase(self._state)
        self._file_list = FileListFrame(file_frame, file_db, self)
        self._file_details = FileInfoFrame(file_frame, file_db)

        fortran_frame = tk.Frame(self._notebook)
        self._notebook.add(fortran_frame, text="Fortran view")

        fortran_db = FortranWorkingState(self._state)
        self._unit_list = UnitListFrame(fortran_frame, fortran_db, self)
        self._unit_details = UnitInfoFrame(fortran_frame, fortran_db, self)

    def exit(self):
        self._root.quit()

    def change_file(self, filename: Path):
        self._file_list.change_file(filename)
        # Use of a magic number below is alarming but ther eis no obvious way
        # to obtain the correct value. You just have to know it.
        #
        # In particular ttk.Notebook.add does not seem to return it.
        #
        self._notebook.select(0)

    def change_file_details(self, filename: Path):
        self._file_details.change_file(filename)

    def change_unit(self, unit: str):
        self._unit_list.change_unit(unit)

    def change_unit_details(self, unit: str):
        self._unit_details.update_info(unit)


class MenuBar(tk.Menu):
    def __init__(self, parent: tk.Tk, window: ExplorerWindow):
        super().__init__(parent)
        parent.config(menu=self)

        self._app_menu = tk.Menu(self, tearoff=0)
        self._app_menu.add_command(label='Exit', command=window.exit)
        self.add_cascade(label='Application', menu=self._app_menu)


class FileListFrame(tk.Listbox):
    def __init__(self, parent: tk.Frame,
                 file_db: FileInfoDatabase,
                 window: ExplorerWindow):
        super().__init__(parent, selectmode=tk.BROWSE, width=40)
        self._window = window

        self.pack(side=tk.LEFT, fill=tk.BOTH)
        self.bind('<ButtonRelease-1>', self._file_click)
        self._index_map = {}
        index = 1
        for file_info in file_db:
            self.insert(index, file_info.filename)
            self._index_map[file_info.filename] = index - 1
            index += 1

    def change_file(self, filename: Path):
        self.selection_set(self._index_map[filename])
        self._window.change_file_details(filename)

    def _file_click(self, event):
        selection = self.get(self.curselection())
        self._window.change_file_details(Path(selection))


class FileInfoFrame(tk.Frame):
    """
    Details of a File.
    """
    def __init__(self, parent: tk.Frame, file_db: FileInfoDatabase):
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


class UnitListFrame(tk.Listbox):
    def __init__(self, parent: tk.Frame,
                 fortran_db: FortranWorkingState,
                 window: ExplorerWindow):
        super().__init__(parent, selectmode=tk.BROWSE)
        self._window = window

        self.pack(side=tk.LEFT, fill=tk.BOTH)
        self.bind('<ButtonRelease-1>', self._fortran_click)
        self._index_map = {}
        index = 1
        for unit_info in fortran_db:
            self.insert(index, unit_info.unit.name)
            self._index_map[unit_info.unit.name] = index - 1
            index += 1

    def change_unit(self, name: str):
        try:
            self.selection_set(self._index_map[name])
            self._window.change_unit_details(name)
        except KeyError:
            message = f"Program unit '{name}' is not in the database."
            messagebox.showerror('Error', message)

    def _fortran_click(self, event):
        selection = self.get(self.curselection())
        self._window.change_unit_details(selection)


class UnitInfoFrame(tk.Frame):
    """
    Details of a Fortran program unit.
    """
    def __init__(self, parent: tk.Frame,
                 fortran_db: FortranWorkingState,
                 window: ExplorerWindow):
        super().__init__(parent)
        self.pack(side=tk.LEFT, fill=tk.Y)

        self._parent = parent
        self._fortran_db = fortran_db
        self._window = window

        tk.Label(self, text='Found in').grid(row=0, column=0)
        self._found_in_field = tk.Listbox(self, selectmode=tk.BROWSE, width=40)
        self._found_in_field.grid(row=1, column=0)
        self._found_in_field.config(cursor='X_cursor')
        self._found_in_field.bind('<Double-Button-1>', self._select_file)

        tk.Label(self, text='Prerequisites').grid(row=0, column=1)
        self._prerequisite_field = tk.Listbox(self, selectmode=tk.BROWSE)
        self._prerequisite_field.grid(row=1, column=1)
        self._prerequisite_field.config(cursor='X_cursor')
        self._prerequisite_field.bind('<Double-Button-1>',
                                      self._select_prerequisite)

        tk.Label(self,
                 text="Double-click with cross pointer").grid(row=2,
                                                              column=0,
                                                              columnspan=2)

    def update_info(self, name: str) -> None:
        self._found_in_field.delete(0, tk.END)
        self._prerequisite_field.delete(0, tk.END)
        for unit_info in self._fortran_db.get_program_unit(name):
            self._found_in_field.insert(tk.END, unit_info.unit.found_in)

            # TODO: This is obviously not right, it concatenates all
            #       dependencies from all instances of the module.
            #
            for unit in unit_info.depends_on:
                self._prerequisite_field.insert(tk.END, unit)

    def _select_file(self, event):
        selected = self._found_in_field.curselection()
        selection = self._found_in_field.get(selected)
        self._window.change_file(Path(selection))

    def _select_prerequisite(self, event):
        selected = self._prerequisite_field.curselection()
        selection = self._prerequisite_field.get(selected)
        self._window.change_unit(selection)

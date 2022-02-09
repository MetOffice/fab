# Todo: Commented out because it's using modules that no longer exist, so mypy is failing.
#       We will be revisiting this.
# ##############################################################################
# # (c) Crown copyright Met Office. All rights reserved.
# # For further details please refer to the file COPYRIGHT
# # which you should have received as part of this distribution
# ##############################################################################
# """
# GUI for the database explorer.
# """
# from pathlib import Path
# import tkinter as tk
# import tkinter.messagebox as tkm
# import tkinter.ttk as ttk
# from typing import Dict
#
# from fab.database import FileInfoDatabase, StateDatabase
# from fab.tasks.fortran import FortranWorkingState
#
#
# def entry() -> None:
#     """
#     Entry point for Fab database exploration tool.
#     """
#     import argparse
#     import fab
#     from fab.database import SqliteStateDatabase
#
#     description = "Explore a Fab state database."
#     parser = argparse.ArgumentParser(add_help=False,
#                                      description=description)
#     # We add our own help so as to capture as many permutations of how people
#     # might ask for help. The default only looks for a subset.
#     parser.add_argument('-h', '-help', '--help', action='help',
#                         help="Print this help and exit")
#     parser.add_argument('-V', '--version', action='version',
#                         version=fab.__version__,
#                         help="Print version identifier and exit")
#     parser.add_argument('-w', '--workspace', metavar='PATH', type=Path,
#                         default=Path.cwd() / 'working',
#                         help="Directory containing working files.")
#     arguments = parser.parse_args()
#
#     state = SqliteStateDatabase(arguments.workspace)
#     window = ExplorerWindow(state)
#     window.mainloop()
#
#
# class ExplorerWindow(tk.Frame):
#     """
#     Main window of the database explorer.
#     """
#     def __init__(self, state: StateDatabase):
#         self._root = tk.Tk()
#         self._root.title("Fab Database Explorer")
#         self._root.resizable(True, True)
#         super().__init__(self._root)
#         self.pack(expand=True, fill=tk.BOTH)
#
#         self._menu_bar = MenuBar(self._root, self)
#
#         self._tabs = TabManager(self, state)
#         self._tabs.pack(side=tk.TOP, expand=True, fill=tk.BOTH)
#
#     def exit(self):
#         self._root.quit()
#
#
# class MenuBar(tk.Menu):
#     def __init__(self, parent: tk.Tk, window: ExplorerWindow):
#         super().__init__(parent)
#         parent.config(menu=self)
#
#         self._app_menu = tk.Menu(self, tearoff=0)
#         self._app_menu.add_command(label='Exit', command=window.exit)
#         self.add_cascade(label='Application', menu=self._app_menu)
#
#
# class TabManager(ttk.Notebook):
#     def __init__(self, parent: tk.Frame, state: StateDatabase):
#         super().__init__(parent)
#
#         self._id_map: Dict[str, int] = {}
#
#         self._file_frame = FileTab(self, state)
#         self.add(self._file_frame, text="File view")
#         self._id_map['file'] = 0
#
#         fortran_frame = FortranTab(self, state)
#         self.add(fortran_frame, text="Fortran view")
#         self._id_map['fortran'] = 1
#
#     def select_tab(self, identifier: str) -> None:
#         self.select(self._id_map[identifier])
#
#     def goto_file(self, filename: Path) -> None:
#         self.select(self._id_map['file'])
#         self._file_frame.select_file(filename)
#
#
# class FileTab(tk.Frame):
#     def __init__(self, parent: ttk.Notebook, database: StateDatabase, ):
#         super().__init__(parent)
#
#         file_db = FileInfoDatabase(database)
#
#         self._file_list = FileListFrame(self, file_db)
#         self._file_list.pack(side=tk.LEFT, padx=5, pady=5,
#                              fill=tk.BOTH, expand=True)
#
#         self._file_details = FileInfoFrame(self, file_db)
#         self._file_details.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
#
#         self.select_file(self._file_list.get_selected())
#
#     def select_file(self, filename: Path) -> None:
#         self._file_list.select(filename)
#         self._file_details.select(filename)
#
#
# class FileListFrame(tk.Listbox):
#     def __init__(self, parent: FileTab, file_db: FileInfoDatabase):
#         super().__init__(parent, selectmode=tk.BROWSE, width=40)
#         self._parent = parent
#
#         self.bind('<ButtonRelease-1>', self._click)
#         self._index_map: Dict[Path, int] = {}
#         index = 0
#         for file_info in file_db:
#             self.insert(index, file_info.filename)
#             self._index_map[file_info.filename] = index
#             index += 1
#         self.selection_set(0)
#
#     def get_selected(self) -> Path:
#         return Path(self.get(self.curselection()))
#
#     def select(self, filename: Path) -> None:
#         self.selection_set(self._index_map[filename])
#
#     def _click(self, event):
#         self._parent.select_file(self.get_selected())
#
#
# class FileInfoFrame(tk.Frame):
#     """
#     Details of a File.
#     """
#     def __init__(self, parent: tk.Frame, file_db: FileInfoDatabase):
#         super().__init__(parent)
#         self._file_db = file_db
#
#         tk.Label(self, text='Hash :').grid(row=0, column=0, sticky=tk.E)
#         self._hash_field = tk.Entry(self, width=10)
#         self._hash_field.grid(row=0, column=1, sticky=tk.W)
#
#     def select(self, filename: Path):
#         info = self._file_db.get_file_info(filename)
#         self._hash_field.delete(0, tk.END)
#         self._hash_field.insert(0, str(info.adler32))
#
#
# class FortranTab(tk.Frame):
#     def __init__(self, parent: TabManager, database: StateDatabase, ):
#         super().__init__(parent)
#         self._parent = parent
#
#         fortran_db = FortranWorkingState(database)
#
#         self.rowconfigure(0, weight=1)
#         self.columnconfigure(1, weight=1)
#
#         self._unit_name = UnitNameFrame(self, fortran_db)
#         self._unit_name.grid(row=0, column=0, padx=5, pady=5,
#                              sticky=tk.N+tk.S)
#
#         self._unit_filename = UnitFileFrame(self, fortran_db)
#         self._unit_filename.grid(row=0, column=1, padx=5, pady=5,
#                                  sticky=tk.N+tk.E+tk.S+tk.W)
#
#         self._unit_details = UnitInfoFrame(self, fortran_db)
#         self._unit_details.grid(row=0, column=2, padx=5, pady=5,
#                                 sticky=tk.NE+tk.SE)
#
#         message = "Single-click to select." \
#             + " Cross pointer indicates double-click to jump"
#         instructions = tk.Label(self, text=message)
#         instructions.grid(row=1, column=0, columnspan=3, sticky=tk.E+tk.W)
#
#         self.select_unit(self._unit_name.get_selected_unit())
#
#     def select_unit(self, unit_name: str) -> None:
#         if self._unit_name.select(unit_name):
#             self._unit_filename.update_with_unit(unit_name)
#             selected = self._unit_filename.get_selected_file()
#             self._unit_details.update_with_file(unit_name, selected)
#
#     def select_file(self, filename: Path) -> None:
#         self._unit_filename.select(filename)
#         selected = self._unit_name.get_selected_unit()
#         self._unit_details.update_with_file(selected, filename)
#
#     def goto_file(self, filename: Path) -> None:
#         self._parent.goto_file(filename)
#
#
# class UnitNameFrame(tk.Frame):
#     def __init__(self, parent: FortranTab, fortran_db: FortranWorkingState):
#         super().__init__(parent)
#         self._parent = parent
#         self._fortran_db = fortran_db
#
#         tk.Label(self, text="Program unit").pack(side=tk.TOP)
#
#         self._unit_list = tk.Listbox(self,
#                                      exportselection=0,
#                                      selectmode=tk.BROWSE)
#         self._unit_list.pack(side=tk.TOP, fill=tk.Y, expand=True)
#         self._unit_list.bind('<ButtonRelease-1>', self._click_unit)
#         self._unit_index_map: Dict[str, int] = {}
#         index = 0
#         current_unit = ''
#         for unit_info in fortran_db:
#             if unit_info.unit.name != current_unit:
#                 current_unit = unit_info.unit.name
#                 self._unit_list.insert(index, current_unit)
#                 self._unit_index_map[current_unit] = index
#                 index += 1
#         self._unit_list.selection_set(0)
#
#     def get_selected_unit(self) -> str:
#         return self._unit_list.get(self._unit_list.curselection())
#
#     def select(self, unit_name: str) -> bool:
#         if unit_name in self._unit_index_map:
#             self._unit_list.selection_clear(self._unit_list.curselection())
#             self._unit_list.selection_set(self._unit_index_map[unit_name])
#             return True
#         else:
#             tkm.showerror("Error from Fab Explorer",
#                           f"Program unit '{unit_name}' not found in database.")
#             return False
#
#     def _click_unit(self, event):
#         self._parent.select_unit(self.get_selected_unit())
#
#
# class UnitFileFrame(tk.Frame):
#     def __init__(self, parent: FortranTab, fortran_db: FortranWorkingState):
#         super().__init__(parent)
#         self._parent = parent
#         self._fortran_db = fortran_db
#
#         tk.Label(self, text="Found in file").pack(side=tk.TOP)
#
#         self._file_index_map: Dict[Path, int] = {}
#         self._found_in_field = tk.Listbox(self,
#                                           exportselection=0,
#                                           selectmode=tk.BROWSE,
#                                           width=40)
#         self._found_in_field.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
#         self._found_in_field.config(cursor='X_cursor')
#         self._found_in_field.bind('<ButtonRelease-1>', self._click)
#         self._found_in_field.bind('<Double-Button-1>', self._double_click)
#
#     def update_with_unit(self, unit: str) -> None:
#         self._file_index_map = {}
#         index = 0
#         self._found_in_field.delete(0, tk.END)
#         for info in self._fortran_db.get_program_unit(unit):
#             self._found_in_field.insert(tk.END, info.unit.found_in)
#             self._file_index_map[info.unit.found_in] = index
#             index += 1
#         self._found_in_field.selection_set(0)
#
#     def get_selected_file(self) -> Path:
#         selected = self._found_in_field.curselection()
#         return Path(self._found_in_field.get(selected))
#
#     def select(self, filename: Path) -> None:
#         self._found_in_field.selection_set(self._file_index_map[filename])
#
#     def _click(self, event) -> None:
#         self._parent.select_file(self.get_selected_file())
#
#     def _double_click(self, event) -> None:
#         self._parent.goto_file(self.get_selected_file())
#
#
# class UnitInfoFrame(tk.Frame):
#     """
#     Details of a Fortran program unit.
#     """
#     def __init__(self, parent: FortranTab, fortran_db: FortranWorkingState):
#         super().__init__(parent)
#         self._parent = parent
#         self._fortran_db = fortran_db
#
#         self.rowconfigure(1, weight=1)
#
#         tk.Label(self, text='Prerequisites').grid(row=0, column=0)
#
#         self._prerequisite_field = tk.Listbox(self, selectmode=tk.BROWSE)
#         self._prerequisite_field.grid(row=1, column=0, sticky=tk.N+tk.S)
#         self._prerequisite_field.config(cursor='X_cursor')
#         self._prerequisite_field.bind('<Double-Button-1>', self._double_click)
#
#     def update_with_file(self, unit: str, filename: Path) -> None:
#         self._prerequisite_field.delete(0, tk.END)
#         for info in self._fortran_db.get_program_unit(unit):
#             if info.unit.found_in == filename:
#                 for prereq in info.depends_on:
#                     self._prerequisite_field.insert(tk.END, prereq)
#         self._prerequisite_field.selection_set(0)
#
#     def get_selected_prereq(self) -> str:
#         selected = self._prerequisite_field.curselection()
#         return self._prerequisite_field.get(selected)
#
#     def _double_click(self, event) -> None:
#         self._parent.select_unit(self.get_selected_prereq())

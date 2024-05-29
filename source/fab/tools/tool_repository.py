##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the ToolRepository class.
'''

# We can't declare _singleton and __new__() using ToolRepository, but
# it is allowed if we use this import:
from __future__ import annotations

import logging
from typing import Any, Type

from fab.tools.tool import Tool
from fab.tools.categories import Categories
from fab.tools.linker import Linker
from fab.tools.versioning import Fcm, Git, Subversion


class ToolRepository(dict):
    '''This class implements the tool repository. It stores a list of
    tools for various categories. For each compiler, it will automatically
    create a tool called "linker-{compiler-name}" which can be used for
    linking with the specified compiler.
    '''

    _singleton: None | ToolRepository = None

    def __new__(cls) -> ToolRepository:
        '''Singleton access. Changes the value of _singleton so that the
        constructor can verify that it is indeed called from here.
        '''
        if not cls._singleton:
            cls._singleton = super().__new__(cls)

        return cls._singleton

    def __init__(self):
        # Note that in this singleton pattern the constructor is called each
        # time the instance is requested (since we overwrite __new__). But
        # we only want to initialise the instance once, so let the constructor
        # not do anything if the singleton already exists:
        if ToolRepository._singleton:
            return

        self._logger = logging.getLogger(__name__)
        super().__init__()

        # Create the list that stores all tools for each category:
        for category in Categories:
            self[category] = []

        # Add the FAB default tools:
        # TODO: sort the defaults so that they actually work (since not all
        # tools FAB knows about are available). For now, disable Fpp:
        # We get circular dependencies if imported at top of the file:
        # pylint: disable=import-outside-toplevel
        from fab.tools import (Ar, Cpp, CppFortran, Gcc, Gfortran,
                               Icc, Ifort, Psyclone, Rsync)

        for cls in [Gcc, Icc, Gfortran, Ifort, Cpp, CppFortran,
                    Fcm, Git, Subversion, Ar, Psyclone, Rsync]:
            self.add_tool(cls)

    def add_tool(self, cls: Type[Any]):
        '''Creates an instance of the specified class and adds it
        to the tool repository.

        :param cls: the tool to instantiate.
        '''

        # Note that we cannot declare `cls` to be `Type[Tool]`, since the
        # Tool constructor requires arguments, but the classes used here are
        # derived from Tool which do not require any arguments (e.g. Ifort)

        tool = cls()
        # We do not test if a tool is actually available. The ToolRepository
        # contains the tools that FAB knows about. It is the responsibility
        # of the ToolBox to make sure only available tools are added.
        self[tool.category].append(tool)

        # If we have a compiler, add the compiler as linker as well
        if tool.is_compiler:
            linker = Linker(name=f"linker-{tool.name}", compiler=tool)
            self[linker.category].append(linker)

    def get_tool(self, category: Categories, name: str) -> Tool:
        ''':returns: the tool with a given name in the specified category.

        :param category: the name of the category in which to look
            for the tool.
        :param name: the name of the tool to find.

        :raises KeyError: if there is no tool in this category.
        :raises KeyError: if no tool in the given category has the
            requested name.
        '''

        if category not in self:
            raise KeyError(f"Unknown category '{category}' "
                           f"in ToolRepository.get_tool().")
        all_tools = self[category]
        for tool in all_tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Unknown tool '{name}' in category '{category}' "
                       f"in ToolRepository.")

    def set_default_vendor(self, vendor: str):
        '''Sets the default for linker and compilers to be of the
        given vendor.

        :param vendor: the vendor name.
        '''
        for category in [Categories.FORTRAN_COMPILER, Categories.C_COMPILER,
                         Categories.LINKER]:
            all_vendor = [tool for tool in self[category]
                          if tool.vendor == vendor]
            if len(all_vendor) == 0:
                raise RuntimeError(f"Cannot find '{category}' "
                                   f"with vendor '{vendor}'.")
            tool = all_vendor[0]
            if tool != self[category][0]:
                self[category].remove(tool)
                self[category].insert(0, tool)

    def get_default(self, category: Categories):
        '''Returns the default tool for a given category, which is just
        the first tool in the category.

        :param category: the category for which to return the default tool.

        :raises KeyError: if the category does not exist.
        '''

        if not isinstance(category, Categories):
            raise RuntimeError(f"Invalid category type "
                               f"'{type(category).__name__}'.")
        return self[category][0]

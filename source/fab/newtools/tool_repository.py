##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the ToolRepository class.
'''

from fab.newtools import Categories, Cpp, Fpp, Gcc, Gfortran, Icc, Ifort


class ToolRepository(dict):
    '''This class implements the tool repository. It stores a list of
    tools for various categories.
    '''

    _singleton = None

    @staticmethod
    def get():
        '''Singleton access. Changes the value of _singleton so that the
        constructor can verify that it is indeed called from here.
        '''
        if ToolRepository._singleton is None:
            ToolRepository._singleton = "FROM_GET"
            ToolRepository._singleton = ToolRepository()
        return ToolRepository._singleton

    def __init__(self):
        # Check if the constuctor is called from 'get':
        if ToolRepository._singleton != "FROM_GET":
            raise RuntimeError("You must use 'ToolRepository.get()' to get "
                               "the singleton instance.")
        super().__init__()
        # The first entry is the default
        self[Categories.C_COMPILER] = [Gcc(), Icc()]
        self[Categories.FORTRAN_COMPILER] = [Gfortran(), Ifort()]
        self[Categories.FORTRAN_PREPROCESSOR] = [Fpp(), Cpp()]

    def get_tool(self, category: Categories, name: str):
        '''Returns the tool with a given name in the specified category.

        :param category: the name of the category in which to look
            for the tool.
        :param name: the name of the tool to find.

        :raises KeyError: if the category is not known.
        :raises KeyError: if no tool in the given category has the
            requested name.
        '''

        if category not in self:
            raise KeyError(f"Unknown category '{category}' "
                           f"in ToolRepository.get.")
        all_tools = self[category]
        for tool in all_tools:
            if tool.name == name:
                return tool
        raise KeyError(f"Unknown tool '{name}' in category '{category}' "
                       f"in ToolRepository.")

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

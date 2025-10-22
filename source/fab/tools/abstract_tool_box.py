##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the AbstractToolBox class.
'''

from abc import ABC, abstractmethod
from typing import Optional

from fab.tools.category import Category
from fab.tools.tool import Tool


class AbstractToolBox(ABC):
    '''This is the abstract base class for the ToolBox class.
    '''

    @abstractmethod
    def has(self, category: Category) -> bool:
        '''
        :returns: whether this tool box has a tool of the specified
            category or not.
        '''

    @abstractmethod
    def add_tool(self, tool: Tool,
                 silent_replace: bool = False) -> None:
        '''Adds a tool for a given category.

        :param tool: the tool to add.
        :param silent_replace: if set, no warning will be printed
            if an existing tool is replaced.

        :raises RuntimeError: if the tool to be added is not available.
        '''

    @abstractmethod
    def get_tool(self, category: Category,
                 mpi: Optional[bool] = None,
                 openmp: Optional[bool] = None,
                 enforce_fortran_linker: Optional[bool] = None) -> Tool:
        '''Returns the tool for the specified category.

        :param category: the name of the category in which to look
            for the tool.
        :param mpi: if no compiler or linker is explicitly specified in this
            tool box, use the MPI and OpenMP setting to find an appropriate
            default from the tool repository.
        :param mpi: if no compiler or linker is explicitly specified in this
            tool box, use the MPI and OpenMP setting to find an appropriate
            default from the tool repository.
        :param enforce_fortran_linker: if a linker is request, this flag
            is used to specify if a Fortran-based linker is required.
            Otherwise, a C-based linker will be returned.

        :raises KeyError: if the category is not known.
        '''

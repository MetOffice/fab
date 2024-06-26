##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains the ToolBox class.
'''

import warnings
from typing import Dict

from fab.tools.category import Category
from fab.tools.tool import Tool
from fab.tools.tool_repository import ToolRepository


class ToolBox:
    '''This class implements the tool box. It stores one tool for each
    category to be used in a FAB build.
    '''

    def __init__(self) -> None:
        self._all_tools: Dict[Category, Tool] = {}

    def __getitem__(self, category: Category) -> Tool:
        '''A convenience function for get_tool.'''
        return self.get_tool(category)

    def add_tool(self, tool: Tool,
                 silent_replace: bool = False) -> None:
        '''Adds a tool for a given category.

        :param tool: the tool to add.
        :param silent_replace: if set, no warning will be printed
            if an existing tool is replaced.

        :raises RuntimeError: if the tool to be added is not available.
        '''
        if not tool.is_available:
            raise RuntimeError(f"Tool '{tool}' is not available.")

        if tool.category in self._all_tools and not silent_replace:
            warnings.warn(f"Replacing existing tool "
                          f"'{self._all_tools[tool.category]}' with "
                          f"'{tool}'.")
        self._all_tools[tool.category] = tool

    def get_tool(self, category: Category) -> Tool:
        '''Returns the tool for the specified category.

        :param category: the name of the category in which to look
            for the tool.

        :raises KeyError: if the category is not known.
        '''

        if category in self._all_tools:
            return self._all_tools[category]

        # No tool was specified for this category, get the default tool
        # from the ToolRepository:
        tr = ToolRepository()
        return tr.get_default(category)

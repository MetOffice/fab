##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for all tools, i.e. compiler,
preprocessor, linker, archiver, Psyclone, rsync, versioning tools.

Each tool belongs to one category (e.g. FORTRAN_COMPILER). This category
is used when adding a tool to a ToolRepository or ToolBox.
It provides basic support for running a binary, and keeping track if
a tool is actually available.
"""

from pathlib import Path
from typing import List, Optional, Union

from fab.tools.category import Category
from fab.tools.tool_with_flags import ToolWithFlags


class CompilerSuiteTool(ToolWithFlags):
    '''A tool that is part of a compiler suite (typically compiler
    and linker).

    :param name: name of the tool.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite.
    :param category: the Category to which this tool belongs.
    :param availability_option: a command line option for the tool to test
        if the tool is available on the current system. Defaults to
        `--version`.
    '''
    def __init__(
            self,
            name: str,
            exec_name: Union[str, Path],
            suite: str,
            category: Category,
            availability_option: Optional[Union[str,
                                                List[str]]] = None) -> None:
        super().__init__(name, exec_name, category,
                         availability_option=availability_option)
        self._suite = suite

    @property
    def suite(self) -> str:
        ''':returns: the compiler suite of this tool.'''
        return self._suite

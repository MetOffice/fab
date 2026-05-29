##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the class to interface with pkg-config.
"""

from typing import List

from fab.tools.category import Category
from fab.tools.tool_with_flags import ToolWithFlags


class PkgConfig(ToolWithFlags):
    '''This class implements a simple interface to `pkg-config`. PkgConfig is
    not added to the ToolRepository, it is intended for site-specific
    configurations to create an instance for each required package.

    :param name: the name of the package. It is the responsibility of the
        user to ensure that package is really available.

    '''

    def __init__(self, name: str):
        super().__init__(f"pkg-config({name})", "pkg-config", Category.MISC)
        self._package = name

    def get_compiler_flags(self) -> List[str]:
        """
        :returns: the compilation flags to use for the specified package.
        """
        flags = self.run(additional_parameters=[self._package, "--cflags"])
        return flags.split()

    def get_linker_flags(self) -> List[str]:
        """
        :returns: the linker flags to use for the specified package.
        """
        flags = self.run(additional_parameters=[self._package, "--libs"])
        return flags.split()

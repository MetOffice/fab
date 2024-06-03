##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any Linker.
"""

import os
from pathlib import Path
from typing import cast, List, Optional

from fab.tools.categories import Categories
from fab.tools.compiler import Compiler
from fab.tools.tool import VendorTool


class Linker(VendorTool):
    '''This is the base class for any Linker. If a compiler is specified,
    its name, executable, and vendor will be used for the linker (if not
    explicitly set in the constructor).

    :param name: the name of the linker.
    :param exec_name: the name of the executable.
    :param vendor: optional, the name of the vendor.
    :param compiler: optional, a compiler instance
    :param output_flag: flag to use to specify the output name.
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: Optional[str] = None,
                 exec_name: Optional[str] = None,
                 vendor: Optional[str] = None,
                 compiler: Optional[Compiler] = None,
                 output_flag: str = "-o"):
        if (not name or not exec_name or not vendor) and not compiler:
            raise RuntimeError("Either specify name, exec name, and vendor "
                               "or a compiler when creating Linker.")
        # Make mypy happy, since it can't work out otherwise if these string
        # variables might still be None :(
        compiler = cast(Compiler, compiler)
        if not name:
            name = compiler.name
        if not exec_name:
            exec_name = compiler.exec_name
        if not vendor:
            vendor = compiler.vendor
        self._output_flag = output_flag
        super().__init__(name, exec_name, vendor, Categories.LINKER)
        self._compiler = compiler
        self.flags.extend(os.getenv("LDFLAGS", "").split())

    def check_available(self) -> bool:
        '''
        :returns: whether the linker is available or not. We do this
            by requesting the linker version.
        '''
        if self._compiler:
            return self._compiler.check_available()

        try:
            # We don't actually care about the result
            self.run("--version")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    def link(self, input_files: List[Path], output_file: Path,
             add_libs: Optional[List[str]] = None) -> str:
        '''Executes the linker with the specified input files,
        creating `output_file`.

        :param input_files: list of input files to link.
        :param output_file: output file.
        :param add_libs: additional linker flags.

        :returns: the stdout of the link command
        '''
        if self._compiler:
            # Create a copy:
            params = self._compiler.flags[:]
        else:
            params = []
        # TODO: why are the .o files sorted? That shouldn't matter
        params.extend(sorted(map(str, input_files)))
        if add_libs:
            params += add_libs
        params.extend([self._output_flag, str(output_file)])
        return self.run(params)

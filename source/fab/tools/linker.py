##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any Linker.
"""

import os
from pathlib import Path
from typing import cast, Dict, List, Optional
import warnings

from fab.tools.category import Category
from fab.tools.compiler import Compiler
from fab.tools.tool import CompilerSuiteTool


class Linker(CompilerSuiteTool):
    '''This is the base class for any Linker. If a compiler is specified,
    its name, executable, and compile suite will be used for the linker (if
    not explicitly set in the constructor).

    :param name: the name of the linker.
    :param exec_name: the name of the executable.
    :param suite: optional, the name of the suite.
    :param compiler: optional, a compiler instance
    :param output_flag: flag to use to specify the output name.
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: Optional[str] = None,
                 exec_name: Optional[str] = None,
                 suite: Optional[str] = None,
                 compiler: Optional[Compiler] = None,
                 output_flag: str = "-o"):
        if (not name or not exec_name or not suite) and not compiler:
            raise RuntimeError("Either specify name, exec name, and suite "
                               "or a compiler when creating Linker.")
        # Make mypy happy, since it can't work out otherwise if these string
        # variables might still be None :(
        compiler = cast(Compiler, compiler)
        if not name:
            name = compiler.name
        if not exec_name:
            exec_name = compiler.exec_name
        if not suite:
            suite = compiler.suite
        self._output_flag = output_flag
        super().__init__(name, exec_name, suite, Category.LINKER)
        self._compiler = compiler
        self.flags.extend(os.getenv("LDFLAGS", "").split())

        # Maintain a set of flags for common libraries.
        self._lib_flags: Dict[str, List[str]] = {}
        # Allow flags to include before or after any library-specific flags.
        self._pre_lib_flags: List[str] = []
        self._post_lib_flags: List[str] = []

    @property
    def mpi(self) -> bool:
        ''':returns: whether the linker supports MPI or not.'''
        return self._compiler.mpi

    def check_available(self) -> bool:
        '''
        :returns: whether the linker is available or not. We do this
            by requesting the linker version.
        '''
        if self._compiler:
            return self._compiler.check_available()

        return super().check_available()

    def get_lib_flags(self, lib: str) -> List[str]:
        '''Gets the standard flags for a standard library

        :param lib: the library name

        :returns: a list of flags

        :raises RuntimeError: if lib is not recognised
        '''
        try:
            return self._lib_flags[lib]
        except KeyError:
            raise RuntimeError(f"Unknown library name: '{lib}'")

    def add_lib_flags(self, lib: str, flags: List[str],
                      silent_replace: bool = False):
        '''Add a set of flags for a standard library

        :param lib: the library name
        :param flags: the flags to use with the library
        :param silent_replace: if set, no warning will be printed when an
            existing lib is overwritten.
        '''
        if lib in self._lib_flags and not silent_replace:
            warnings.warn(f"Replacing existing flags for library {lib}: "
                          f"'{self._lib_flags[lib]}' with "
                          f"'{flags}'.")

        # Make a copy to avoid modifying the caller's list
        self._lib_flags[lib] = flags[:]

    def add_pre_lib_flags(self, flags: List[str]):
        '''Add a set of flags to use before any library-specific flags

        :param flags: the flags to include
        '''
        self._pre_lib_flags.extend(flags)

    def add_post_lib_flags(self, flags: List[str]):
        '''Add a set of flags to use after any library-specific flags

        :param flags: the flags to include
        '''
        self._post_lib_flags.extend(flags)

    def link(self, input_files: List[Path], output_file: Path,
             openmp: bool,
             libs: Optional[List[str]] = None) -> str:
        '''Executes the linker with the specified input files,
        creating `output_file`.

        :param input_files: list of input files to link.
        :param output_file: output file.
        :param openm: whether OpenMP is requested or not.
        :param libs: additional libraries to link with.

        :returns: the stdout of the link command
        '''
        if self._compiler:
            # Create a copy:
            params = self._compiler.flags[:]
            if openmp:
                params.append(self._compiler.openmp_flag)
        else:
            params = []
        # TODO: why are the .o files sorted? That shouldn't matter
        params.extend(sorted(map(str, input_files)))

        if self._pre_lib_flags:
            params.extend(self._pre_lib_flags)
        for lib in (libs or []):
            params.extend(self.get_lib_flags(lib))
        if self._post_lib_flags:
            params.extend(self._post_lib_flags)
        params.extend([self._output_flag, str(output_file)])
        return self.run(params)

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any Linker.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import warnings

from fab.tools.category import Category
from fab.tools.compiler import Compiler
from fab.tools.compiler_wrapper import CompilerWrapper


class Linker(CompilerWrapper):
    '''This is the base class for any Linker. If a compiler is specified,
    its name, executable, and compile suite will be used for the linker (if
    not explicitly set in the constructor).

    :param compiler: optional, a compiler instance
    :param output_flag: flag to use to specify the output name.
    '''

    def __init__(self, compiler: Compiler, output_flag: str = "-o"):
        self._output_flag = output_flag
        super().__init__(
            name=f"linker-{compiler.name}",
            exec_name=compiler.exec_name,
            compiler=compiler,
            category=Category.LINKER,
            mpi=compiler.mpi)

        self._flags.extend(os.getenv("LDFLAGS", "").split())

        # Maintain a set of flags for common libraries.
        self._lib_flags: Dict[str, List[str]] = {}
        # Allow flags to include before or after any library-specific flags.
        self._pre_lib_flags: List[str] = []
        self._post_lib_flags: List[str] = []

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
        # Don't need to add compiler's flags, they are added by CompilerWrapper.
        params: List[Union[str, Path]] = []
        if openmp:
            params.append(self._compiler.openmp_flag)

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

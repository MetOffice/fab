##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any Linker.
"""

import os
from pathlib import Path
from typing import cast, Dict, List, Optional, Union
import warnings

from fab.tools.category import Category
from fab.tools.compiler import Compiler
from fab.tools.compiler_wrapper import CompilerWrapper


class Linker(CompilerWrapper):
    '''This is the base class for any Linker.

    :param compiler: a compiler or linker instance
    :param output_flag: flag to use to specify the output name.
    '''

    def __init__(self, compiler: Compiler, output_flag: str = "-o"):

        super().__init__(
            name=f"linker-{compiler.name}",
            exec_name=compiler.exec_name,
            compiler=compiler,
            category=Category.LINKER,
            mpi=compiler.mpi)

        self._output_flag = output_flag
        self.add_flags(os.getenv("LDFLAGS", "").split())

        # Maintain a set of flags for common libraries.
        self._lib_flags: Dict[str, List[str]] = {}
        # Allow flags to include before or after any library-specific flags.
        self._pre_lib_flags: List[str] = []
        self._post_lib_flags: List[str] = []

    def get_output_flag(self) -> str:
        ''':returns: the flag that is used to specify the output name.
        '''
        if self._output_flag:
            return self._output_flag
        if not self.compiler.category == Category.LINKER:
            raise RuntimeError(f"No output flag found for linker {self.name}.")

        linker = cast(Linker, self.compiler)
        return linker.get_output_flag()

    def get_lib_flags(self, lib: str) -> List[str]:
        '''Gets the standard flags for a standard library

        :param lib: the library name

        :returns: a list of flags

        :raises RuntimeError: if lib is not recognised
        '''
        try:
            return self._lib_flags[lib]
        except KeyError:
            # If a lib is not defined here, but this is a wrapper around
            # another linker, return the result from the wrapped linker
            if self.compiler.category is Category.LINKER:
                linker = cast(Linker, self.compiler)
                return linker.get_lib_flags(lib)
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

    def get_pre_link_flags(self) -> List[str]:
        '''Returns the list of pre-link flags. It will concatenate the
        flags for this instance with all potentially wrapper linkers.
        This wrapper's flag will come first - the assumption is that
        the pre-link flags are likely paths, so we need a wrapper to
        be able to put a search path before the paths from a wrapped
        linker.

        :returns: List of pre-link flags of this linker and all
            wrapped linkers
        '''
        params: List[str] = []

        if self._pre_lib_flags:
            params.extend(self._pre_lib_flags)
        if self.compiler.category == Category.LINKER:
            # If we are wrapping a linker, get the wrapped linker's
            # pre-link flags and append them to the end (so the linker
            # wrapper's settings come first)
            linker = cast(Linker, self.compiler)
            params.extend(linker.get_pre_link_flags())
        return params

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

        params: List[Union[str, Path]] = []

        if openmp:
            compiler = self.compiler
            while compiler.category == Category.LINKER:
                linker = cast(Linker, compiler)
                compiler = linker.compiler

            params.append(compiler.openmp_flag)

        # TODO: why are the .o files sorted? That shouldn't matter
        params.extend(sorted(map(str, input_files)))
        params.extend(self.get_pre_link_flags())

        for lib in (libs or []):
            params.extend(self.get_lib_flags(lib))

        if self._post_lib_flags:
            params.extend(self._post_lib_flags)
        params.extend([self.get_output_flag(), str(output_file)])

        return self.run(params)

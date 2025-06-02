##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any Linker.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Union
import warnings

from fab.tools.category import Category
from fab.tools.compiler import Compiler
from fab.tools.tool import CompilerSuiteTool


class Linker(CompilerSuiteTool):
    '''This is the base class for any Linker. It takes an existing compiler
    instance as parameter, and optional another linker. The latter is used
    to get linker settings - for example, linker-mpif90-gfortran will use
    mpif90-gfortran as compiler (i.e. to test if it is available and get
    compilation flags), and linker-gfortran as linker. This way a user
    only has to specify linker flags in the most basic class (gfortran),
    all other linker wrapper will inherit the settings.

    :param compiler: a compiler instance
    :param linker: an optional linker instance
    :param name: name of the linker

    :raises RuntimeError: if both compiler and linker are specified.
    :raises RuntimeError: if neither compiler nor linker is specified.
    '''

    def __init__(self, compiler: Compiler,
                 linker: Optional[Linker] = None,
                 name: Optional[str] = None):

        self._compiler = compiler
        self._linker = linker

        if not name:
            name = f"linker-{compiler.name}"

        super().__init__(
            name=name,
            exec_name=compiler.exec_name,
            suite=self.suite,
            category=Category.LINKER)

        self.add_flags(os.getenv("LDFLAGS", "").split())

        # Maintain a set of flags for common libraries.
        self._lib_flags: Dict[str, List[str]] = {}
        # Allow flags to include before or after any library-specific flags.
        self._pre_lib_flags: List[str] = []
        self._post_lib_flags: List[str] = []

    def check_available(self) -> bool:
        ''':returns: whether this linker is available by asking the wrapped
            linker or compiler.
        '''
        return self._compiler.check_available()

    @property
    def suite(self) -> str:
        ''':returns: the suite this linker belongs to by getting it from
            the wrapped compiler.'''
        return self._compiler.suite

    @property
    def mpi(self) -> bool:
        ''':returns" whether this linker supports MPI or not by checking
            with the wrapped compiler.'''
        return self._compiler.mpi

    @property
    def openmp(self) -> bool:
        ''':returns: whether this linker supports OpenMP or not by checking
            with the wrapped compiler.'''
        return self._compiler.openmp

    @property
    def output_flag(self) -> str:
        ''':returns: the flag that is used to specify the output name.
        '''
        return self._compiler.output_flag

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
            if self._linker:
                return self._linker.get_lib_flags(lib)
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
        flags for this instance with all potentially wrapped linkers.
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
        if self._linker:
            # If we are wrapping a linker (e.g. linker-mpif90-gfortran
            # wrapping linker-gfortran), get the wrapped linker's
            # pre-link flags and append them to the end. In the example
            # this means that any flags from linker-mpif90-gfortran come
            # before any flags from linker-gfortran, which makes sure
            # that a wrapper can insert new/different search paths
            # (i.e. -L directives) before the wrapper - allowing a
            # wrapper to overwrite libraries from.
            params.extend(self._linker.get_pre_link_flags())
        return params

    def get_post_link_flags(self) -> List[str]:
        '''Returns the list of post-link flags. It will concatenate the
        flags for this instance with all potentially wrapped linkers.
        This wrapper's flag will be added to the end.

        :returns: List of post-link flags of this linker and all
            wrapped linkers
        '''
        params: List[str] = []
        if self._linker:
            # If we are wrapping a linker, get the wrapped linker's
            # post-link flags and add them first (so this linker
            # wrapper's settings come after the setting from the
            # wrapped linker).
            params.extend(self._linker.get_post_link_flags())
        if self._post_lib_flags:
            params.extend(self._post_lib_flags)
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

        params.extend(self._compiler.flags)

        if openmp:
            params.append(self._compiler.openmp_flag)

        # TODO: why are the .o files sorted? That shouldn't matter
        params.extend(sorted(map(str, input_files)))
        params.extend(self.get_pre_link_flags())

        for lib in (libs or []):
            params.extend(self.get_lib_flags(lib))

        params.extend(self.get_post_link_flags())
        params.extend([self.output_flag, str(output_file)])

        return self.run(params)

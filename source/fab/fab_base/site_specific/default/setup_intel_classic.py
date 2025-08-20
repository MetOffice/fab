#!/usr/bin/env python3

'''
This file contains a function that sets the default flags for all
Intel classic based compilers in the ToolRepository (ifort, icc).

This function gets called from the default site-specific config file
'''

import argparse
from typing import cast, Dict, List

from fab.build_config import AddFlags, BuildConfig
from fab.tools import Category, Compiler, Linker, ToolRepository


def setup_intel_classic(build_config: BuildConfig,
                        args: argparse.Namespace) -> Dict[str, List[AddFlags]]:
    # pylint: disable=unused-argument, too-many-locals
    '''
    Defines the default flags for all Intel classic compilers and linkers.

    :param build_config: the Fab build config instance from which
        required parameters can be taken.
    :param argparse.Namespace args: all command line options
    '''

    tr = ToolRepository()
    ifort = tr.get_tool(Category.FORTRAN_COMPILER, "ifort")
    ifort = cast(Compiler, ifort)

    if not ifort.is_available:
        # This can happen if ifort is not in path (in spack environments).
        # To support this common use case, see if mpif90-ifort is available,
        # and initialise this otherwise.
        ifort = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90-ifort")
        ifort = cast(Compiler, ifort)
        if not ifort.is_available:
            # Since some flags depends on version, the code below requires
            # that the intel compiler actually works.
            return {}

    # The base flags
    # ==============
    # The following flags will be applied to all modes:
    ifort.add_flags(["-g", "-traceback"],            "base")

    # The "-assume realloc-lhs" switch causes Intel Fortran prior to v17 to
    # actually implement the Fortran2003 standard. At version 17 it becomes the
    # default behaviour.
    if ifort.get_version() < (17, 0):
        ifort.add_flags(["-assume", "realloc-lhs"], "base")

    # Full debug
    # ==========
    ifort.add_flags(["-O0", "-ftrapuv"],  "full-debug")

    # Fast debug
    # ==========
    ifort.add_flags(["-O2", "-fp-model=strict"], "fast-debug")

    # Production
    # ==========
    ifort.add_flags(["-O3", "-xhost"], "production")

    # Set up the linker
    # =================
    # This will implicitly affect all ifort based linkers, e.g.
    # linker-mpif90-ifort will use these flags as well.
    linker = tr.get_tool(Category.LINKER, f"linker-{ifort.name}")
    linker = cast(Linker, linker)

    # Setup library info, e.g.:
    # linker.add_lib_flags("yaxt", ["-L/some/path", "-lyaxt", "-lyaxt_c"])

    # Add more flags to be always used, e.g.:
    # linker.add_post_lib_flags(["-lstdc++"], "base")

    return {}

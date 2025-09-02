#!/usr/bin/env python3

'''
This file contains a function that sets the default flags for all
GNU based compilers and linkers in the ToolRepository.

This function gets called from the default site-specific config file
'''

import argparse
from typing import cast, Dict, List

from fab.build_config import AddFlags, BuildConfig
from fab.tools import Category, Linker, ToolRepository


def setup_gnu(build_config: BuildConfig,
              args: argparse.Namespace) -> Dict[str, List[AddFlags]]:
    # pylint: disable=unused-argument
    '''
    Defines the default flags for all GNU compilers and linkers.

    :param build_config: the Fab build config instance from which
        required parameters can be taken.
    :param args: all command line options
    '''

    tr = ToolRepository()
    gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "gfortran")

    if not gfortran.is_available:
        gfortran = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90-gfortran")
        if not gfortran.is_available:
            return {}

    # The base flags
    # ==============
    gfortran.add_flags(['-ffree-line-length-none', '-Wall', '-g'],
                       "base")
    runtime = ["-fcheck=all", "-ffpe-trap=invalid,zero,overflow"]
    init = ["-finit-integer=31173",  "-finit-real=snan",
            "-finit-logical=true", "-finit-character=85"]
    # Full debug
    # ==========
    gfortran.add_flags(runtime + ["-O0"] + init, "full-debug")

    # Fast debug
    # ==========
    gfortran.add_flags(runtime + ["-Og"], "fast-debug")

    # Production
    # ==========
    gfortran.add_flags(["-Ofast"], "production")

    # unit-tests
    # ==========
    gfortran.add_flags(runtime + ["-O0"] + init, "unit-tests")

    # Set up the linker
    # =================
    # This will implicitly affect all gfortran based linkers, e.g.
    # linker-mpif90-gfortran will use these flags as well.
    linker = tr.get_tool(Category.LINKER, f"linker-{gfortran.name}")
    linker = cast(Linker, linker)

    # Setup library info, e.g.:
    # linker.add_lib_flags("yaxt", ["-L/some/path", "-lyaxt", "-lyaxt_c"])

    # Add more flags to be always used, e.g.:
    # linker.add_post_lib_flags(["-lstdc++"], "base")

    return {}

#!/usr/bin/env python3

'''
This file contains a function that sets the default flags for all
Intel llvm based compilers and linkers in the ToolRepository (ifx, icx).

This function gets called from the default site-specific config file
'''

import argparse
from typing import cast, Dict, List

from fab.build_config import AddFlags, BuildConfig
from fab.tools import Category, Compiler, Linker, ToolRepository


def setup_intel_llvm(build_config: BuildConfig,
                     args: argparse.Namespace) -> Dict[str, List[AddFlags]]:
    # pylint: disable=unused-argument, too-many-locals
    '''
    Defines the default flags for all Intel llvm compilers.

    :param build_config: the Fab build config instance from which
        required parameters can be taken.
    :param argparse.Namespace args: all command line options
    '''

    tr = ToolRepository()
    ifx = tr.get_tool(Category.FORTRAN_COMPILER, "ifx")
    ifx = cast(Compiler, ifx)

    if not ifx.is_available:
        ifx = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90-ifx")
        ifx = cast(Compiler, ifx)
        if not ifx.is_available:
            return {}

    # The base flags
    # ==============
    # The following flags will be applied to all modes:
    ifx.add_flags(["-g", "-traceback"],            "base")

    # Full debug
    # ==========
    ifx.add_flags(["-O0", "-ftrapuv"],        "full-debug")

    # Fast debug
    # ==========
    ifx.add_flags(["-O2", "-fp-model=strict"], "fast-debug")

    # Production
    # ==========
    ifx.add_flags(["-O3", "-xhost"], "production")

    # Set up the linker
    # =================
    # This will implicitly affect all ifx based linkers, e.g.
    # linker-mpif90-ifx will use these flags as well.
    linker = tr.get_tool(Category.LINKER, f"linker-{ifx.name}")
    linker = cast(Linker, linker)    # Make mypy happy

    # Setup library info, e.g.:
    # linker.add_lib_flags("yaxt", ["-L/some/path", "-lyaxt", "-lyaxt_c"])

    # Add more flags to be always used, e.g.:
    # linker.add_post_lib_flags(["-lstdc++"], "base")

    return {}

#!/usr/bin/env python3

'''
This file contains a function that sets the default flags for the NVIDIA
compilers and linkers in the ToolRepository.

This function gets called from the default site-specific config file
'''

import argparse
from typing import cast, Dict, List

from fab.build_config import AddFlags, BuildConfig
from fab.tools import Category, Compiler, Linker, ToolRepository


def setup_nvidia(build_config: BuildConfig,
                 args: argparse.Namespace) -> Dict[str, List[AddFlags]]:
    # pylint: disable=unused-argument
    '''
    Defines the default flags for nvfortran.

    :param build_config: the Fab build config instance from which
        required parameters can be taken.
    :param args: all command line options
    '''

    tr = ToolRepository()
    nvfortran = tr.get_tool(Category.FORTRAN_COMPILER, "nvfortran")
    nvfortran = cast(Compiler, nvfortran)

    if not nvfortran.is_available:
        nvfortran = tr.get_tool(Category.FORTRAN_COMPILER, "mpif90-nvfortran")
        nvfortran = cast(Compiler, nvfortran)
        if not nvfortran.is_available:
            return {}

    # The base flags
    # ==============
    flags = ["-Mextend",           # 132 characters line length
             "-g", "-traceback",
             ]
    nvfortran.add_flags(flags, "base")

    # Full debug
    # ==========
    nvfortran.add_flags(["-O0", "-fp-model=strict"], "full-debug")

    # Fast debug
    # ==========
    nvfortran.add_flags(["-O2", "-fp-model=strict"], "fast-debug")

    # Production
    # ==========
    nvfortran.add_flags(["-O4"], "production")

    # Set up the linker
    # =================
    # This will implicitly affect all nvfortran based linkers, e.g.
    # linker-mpif90-nvfortran will use these flags as well.
    linker = tr.get_tool(Category.LINKER, f"linker-{nvfortran.name}")
    linker = cast(Linker, linker)

    # Setup library info, e.g.:
    # linker.add_lib_flags("yaxt", ["-L/some/path", "-lyaxt", "-lyaxt_c"])

    # Always link with C++ libs
    # linker.add_post_lib_flags(["-c++libs"], "base")

    return {}

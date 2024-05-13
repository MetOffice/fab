##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''A simple init file to make it shorter to import tools.
'''

from fab.newtools.ar import Ar
from fab.newtools.categories import Categories
from fab.newtools.compiler import (CCompiler, Compiler, FortranCompiler, Gcc,
                                   Gfortran, Icc, Ifort)
from fab.newtools.flags import Flags
from fab.newtools.linker import Linker
from fab.newtools.psyclone import Psyclone
from fab.newtools.preprocessor import Cpp, CppFortran, Fpp, Preprocessor
from fab.newtools.tool import Tool, VendorTool
# Order here is important to avoid a circular import
from fab.newtools.tool_repository import ToolRepository
from fab.newtools.tool_box import ToolBox
from fab.newtools.versioning import Fcm, Git, Subversion, Versioning

__all__ = ["Ar",
           "Categories",
           "CCompiler",
           "Compiler",
           "Cpp",
           "CppFortran",
           "Fcm",
           "Flags",
           "FortranCompiler",
           "Fpp",
           "Gcc",
           "Gfortran",
           "Git",
           "Icc",
           "Ifort",
           "Linker",
           "Preprocessor",
           "Psyclone",
           "Subversion",
           "Tool",
           "ToolBox",
           "ToolRepository",
           "VendorTool",
           "Versioning",
           ]

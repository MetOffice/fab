##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''A simple init file to make it shorter to import tools.
'''

from fab.tools.ar import Ar
from fab.tools.categories import Categories
from fab.tools.compiler import (CCompiler, Compiler, FortranCompiler, Gcc,
                                Gfortran, Icc, Ifort)
from fab.tools.flags import Flags
from fab.tools.linker import Linker
from fab.tools.psyclone import Psyclone
from fab.tools.rsync import Rsync
from fab.tools.preprocessor import Cpp, CppFortran, Fpp, Preprocessor
from fab.tools.tool import Tool, VendorTool
# Order here is important to avoid a circular import
from fab.tools.tool_repository import ToolRepository
from fab.tools.tool_box import ToolBox
from fab.tools.versioning import Fcm, Git, Subversion, Versioning

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
           "Rsync",
           "Subversion",
           "Tool",
           "ToolBox",
           "ToolRepository",
           "VendorTool",
           "Versioning",
           ]

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''A simple init file to make it shorter to import tools.
'''

from fab.tools.ar import Ar
from fab.tools.category import Category
from fab.tools.compiler import (CCompiler, Compiler, FortranCompiler, Gcc,
                                Gfortran, GnuVersionHandling, Icc, Ifort,
                                IntelVersionHandling, MpiGcc, MpiGfortran,
                                MpiIcc, MpiIfort)
from fab.tools.flags import Flags
from fab.tools.linker import Linker
from fab.tools.psyclone import Psyclone
from fab.tools.rsync import Rsync
from fab.tools.preprocessor import Cpp, CppFortran, Fpp, Preprocessor
from fab.tools.tool import Tool, CompilerSuiteTool
# Order here is important to avoid a circular import
from fab.tools.tool_repository import ToolRepository
from fab.tools.tool_box import ToolBox
from fab.tools.versioning import Fcm, Git, Subversion, Versioning

__all__ = ["Ar",
           "Category",
           "CCompiler",
           "Compiler",
           "CompilerSuiteTool",
           "Cpp",
           "CppFortran",
           "Fcm",
           "Flags",
           "FortranCompiler",
           "Fpp",
           "Gcc",
           "Gfortran",
           "Git",
           "GnuVersionHandling",
           "Icc",
           "Ifort",
           "IntelVersionHandling",
           "Linker",
           "MpiGcc",
           "MpiGfortran",
           "MpiIcc",
           "MpiIfort",
           "Preprocessor",
           "Psyclone",
           "Rsync",
           "Subversion",
           "Tool",
           "ToolBox",
           "ToolRepository",
           "Versioning",
           ]

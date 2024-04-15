##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''A simple init file to make it shorter to import tools.
'''

from fab.newtools.compiler import Compiler, Gcc, Gfortran, Icc, Ifort
from fab.newtools.flags import Flags
from fab.newtools.tool import Tool
from fab.newtools.tool_repository import ToolRepository

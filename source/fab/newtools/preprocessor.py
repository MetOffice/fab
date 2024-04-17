##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any preprocessor, and two derived
classes for cpp and fpp.

"""

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Preprocessor(Tool):
    '''This is the base class for any preprocessor.
    '''

    def __init__(self, name: str, exec_name: str, category: Categories):
        super().__init__(name, exec_name, category)
        self._version = None


# ============================================================================
class Cpp(Preprocessor):
    '''Class for cpp.
    '''
    def __init__(self):
        super().__init__("cpp", "cpp", Categories.C_PREPROCESSOR)


# ============================================================================
class Fpp(Preprocessor):
    '''Class for the Fortran-specific preprocessor.
    '''
    def __init__(self):
        super().__init__("fpp", "fpp", Categories.FORTRAN_PREPROCESSOR)
        # TODO: Proper check to be done
        self.is_available = False

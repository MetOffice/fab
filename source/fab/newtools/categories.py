##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This simple module defines an Enum for all allowed categories.
'''

from enum import auto, Enum


class Categories(Enum):
    '''This class defines the allowed tool categories.'''

    C_COMPILER = auto()
    C_PREPROCESSOR = auto()
    FORTRAN_COMPILER = auto()
    FORTRAN_PREPROCESSOR = auto()
    LINKER = auto()
    PSYCLONE = auto()

    def __str__(self):
        '''Simplify the str output by using only the name (e.g. `C_COMPILER`
        instead of `Categories.C_COMPILER)`.'''
        return str(self.name)

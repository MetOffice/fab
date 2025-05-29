##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This simple module defines an Enum for all allowed categories.
'''

from enum import auto, Enum


class Category(Enum):
    '''This class defines the allowed tool categories.'''
    # TODO 311: Allow support for users to add their own tools.

    C_COMPILER = auto()
    C_PREPROCESSOR = auto()
    FORTRAN_COMPILER = auto()
    FORTRAN_PREPROCESSOR = auto()
    LINKER = auto()
    PSYCLONE = auto()
    FCM = auto()
    GIT = auto()
    SUBVERSION = auto()
    AR = auto()
    RSYNC = auto()
    SHELL = auto()
    MISC = auto()

    def __str__(self):
        '''Simplify the str output by using only the name (e.g. `C_COMPILER`
        instead of `Category.C_COMPILER)`.'''
        return str(self.name)

    @property
    def is_compiler(self):
        '''Returns if the category is either a C or a Fortran compiler.'''
        return self in [Category.FORTRAN_COMPILER, Category.C_COMPILER]

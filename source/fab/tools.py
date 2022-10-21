# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Known command line tools whose flags we wish to manage.

"""
from typing import Dict


class Compiler(object):
    """
    A command-line compiler whose flags we wish to manage.

    """
    def __init__(self, exe, compile_flag, module_folder_flag):
        self.exe = exe
        self.compile_flag = compile_flag
        self.module_folder_flag = module_folder_flag
        # We should probably extend this for fPIC, two-stage and optimisation levels.


COMPILERS: Dict[str, Compiler] = {
    'gfortran': Compiler(exe='gfortran', compile_flag='-c', module_folder_flag='-J'),
    'ifort': Compiler(exe='ifort', compile_flag='-c', module_folder_flag='-module'),
}

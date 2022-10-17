# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict


class Compiler(object):

    def __init__(self, exe, compile_flag, module_folder_flag, pic_flag):
        self.exe = exe
        self.compile_flag = compile_flag
        self.module_folder_flag = module_folder_flag
        self.pic_flag = pic_flag


COMPILERS: Dict[str, Compiler] = {
    'gfortran': Compiler(exe='gfortran', compile_flag='-c', module_folder_flag='-J', pic_flag='-fPIC'),
    'ifort': Compiler(exe='ifort', compile_flag='-c', module_folder_flag='-module', pic_flag='-fpic'),
}

# # GFORTRAN = Compiler(exe='gfortran', compile_flag='-c', module_folder_flag='-J', pic_flag='-fPIC')
# # IFORT = Compiler(exe='ifort', compile_flag='-c', module_folder_flag='-module', pic_flag='-fPIC')

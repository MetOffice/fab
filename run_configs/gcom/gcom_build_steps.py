##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import os
from typing import List

from fab.build_config import build_config
from fab.steps import Step
from fab.steps.analyse import analyse
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.preprocess import preprocess_fortran, preprocess_c
from fab.util import common_arg_parser

from grab_gcom import gcom_grab_config


def common_build_steps(fpic=False):

    fpp_flags = [
        '-P',
        '-I$source/gcom/include',
        '-DGC_VERSION="7.6"',
        '-DGC_BUILD_DATE="20220111"',
        '-DGC_DESCRIP="dummy desrip"',
        '-DPREC_64B', '-DMPILIB_32B',
    ]

    fpic = ['-fPIC'] if fpic else []

    with gcom_grab_config as grab_config:
        source_root = grab_config.source_root

    grab_folder(src=source_root),
    find_source_files(),
    preprocess_c(),
    preprocess_fortran(common_flags=fpp_flags),
    analyse(),
    compile_c(common_flags=['-c', '-std=c99'] + fpic),
    compile_fortran(common_flags=fpic),

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from typing import List

from fab.steps import Step
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.preprocess import c_preprocessor, fortran_preprocessor


def common_build_steps(fortran_compiler, fpic=False) -> List[Step]:

    fpp_flags = [
        '-P',
        '-I$source/gcom/include',
        '-DGC_VERSION="7.6"',
        '-DGC_BUILD_DATE="20220111"',
        '-DGC_DESCRIP="dummy desrip"',
        '-DPREC_64B', '-DMPILIB_32B',
    ]

    fpic = ['-fPIC'] if fpic else []

    steps = [
        FindSourceFiles(),
        c_preprocessor(),
        fortran_preprocessor(common_flags=fpp_flags),
        Analyse(),
        CompileC(common_flags=['-c', '-std=c99'] + fpic),
        CompileFortran(compiler=fortran_compiler, common_flags=fpic),
    ]

    return steps

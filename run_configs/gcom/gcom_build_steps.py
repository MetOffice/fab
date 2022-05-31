##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from typing import List

from fab.steps.preprocess import c_preprocessor, fortran_preprocessor

from fab.steps import Step
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.walk_source import FindSourceFiles


def common_build_steps(fpic=False) -> List[Step]:
    steps = [
        FindSourceFiles(),
        c_preprocessor(),
        fortran_preprocessor(
            common_flags=[
                '-P',
                '-I$source/gcom/include',
                '-DGC_VERSION="7.6"',
                '-DGC_BUILD_DATE="20220111"',
                '-DGC_DESCRIP="dummy desrip"',
                '-DPREC_64B', '-DMPILIB_32B',
            ],
        ),
        Analyse(root_symbol=None),  # no program unit, we're not building an exe

        *compilers(fpic=fpic),
    ]

    return steps


def compilers(fpic=False) -> List[Step]:
    fpic = ['-fPIC'] if fpic else []

    return [
        CompileC(common_flags=['-c', '-std=c99'] + fpic),
        CompileFortran(
            compiler='gfortran',
            common_flags=['-c', '-J', '$output'] + fpic),
    ]

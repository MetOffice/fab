#!/usr/bin/env python
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

import os
from pathlib import Path

from fab.builder import Build
from fab.config import Config
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFcm
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import TimerLogger


def gcom_object_archive_config():
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'gcom'

    config = Config(label='gcom object archive', workspace=workspace)

    config.steps = [
        GrabFcm(src='fcm:gcom.xm_tr/build', revision='vn7.6', dst_label="gcom"),
        FindSourceFiles(),
        CPreProcessor(),
        FortranPreProcessor(
            common_flags=[
                '-traditional-cpp', '-P',
                '-I', '$source/gcom/include',
                '-DGC_VERSION="7.6"',
                '-DGC_BUILD_DATE="20220111"',
                '-DGC_DESCRIP="dummy desrip"',
                '-DPREC_64B', '-DMPILIB_32B',
            ],
        ),
        Analyse(root_symbol=None),  # no program unit, we're not building an exe
        CompileC(common_flags=['-c', '-std=c99']),
        CompileFortran(
            compiler=os.path.expanduser('~/.conda/envs/sci-fab/bin/gfortran'),
            common_flags=['-c', '-J', '$output']
        ),
        ArchiveObjects(archiver='ar', output_fpath='$output/libgcom.a'),
    ]

    return config


def main():

    with TimerLogger("gcom build"):
        Build(config=gcom_object_archive_config()).run()


if __name__ == '__main__':
    main()

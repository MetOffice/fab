#!/usr/bin/env python
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

import os
import shutil
from pathlib import Path

from fab.builder import Build
from fab.config import Config
from fab.constants import SOURCE_ROOT
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import TimerLogger


def gcom_object_archive_config():
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'gcom'

    config = Config(label='gcom object archive', workspace=workspace)

    config.grab_config = {("gcom", "~/svn/gcom/trunk/build"), }

    config.steps = [
        FindSourceFiles(workspace / SOURCE_ROOT),  # template?
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

    # ignore this, it's not here
    config = gcom_object_archive_config()
    with TimerLogger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)

    with TimerLogger("gcom build"):
        Build(config=gcom_object_archive_config()).run()

def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


if __name__ == '__main__':
    main()

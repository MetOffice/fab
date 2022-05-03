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
from fab.steps.link_exe import LinkSharedObject
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import FindSourceFiles
from fab.util import time_logger


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


# def gcom_shared_object_config():
#     from fab.dep_tree import by_type
#
#     config = gcom_object_archive_config()
#     config.label = 'gcom shared object'
#
#     # don't pull the source again
#     config.grab_config = None
#
#     # compile with fPIC
#     fc: CompileFortran = list(by_type(config.steps, CompileFortran))[0]
#     fc.flags.common_flags.append('-fPIC')
#
#     cc: CompileC = list(by_type(config.steps, CompileC))[0]
#     cc.flags.common_flags.append('-fPIC')
#
#     # link the object archive
#     config.steps.append(LinkSharedObject(
#         linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
#         output_fpath='$output/libgcom.so'))
#
#     return config


def main():

    # ignore this, it's not here
    config = gcom_object_archive_config()
    with time_logger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)

    #
    # configs = [gcom_object_archive_config(), gcom_shared_object_config()]
    # for config in configs:
    #     with time_logger("gcom build"):
    #         Build(config=config).run()

    with time_logger("gcom build"):
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

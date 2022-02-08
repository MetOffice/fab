#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.builder import Build
from fab.config import ConfigSketch
from fab.constants import SOURCE_ROOT
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkSharedObject
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import GetSourceFiles
from fab.util import time_logger


def gcom_object_archive_config():

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / 'gcom'

    config = ConfigSketch(label='gcom object archive', workspace=workspace)

    config.grab_config = {("gcom", "~/svn/gcom/trunk/build"), }

    config.steps = [
        GetSourceFiles(workspace / SOURCE_ROOT),  # template?
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
        Analyse(),
        CompileC(common_flags=['-c', '-std=c99']),
        CompileFortran(
            compiler=os.path.expanduser('~/.conda/envs/sci-fab/bin/gfortran'),
            common_flags=['-c', '-J', '$output']
        ),
        ArchiveObjects(archiver='ar', output_fpath='$output/libgcom.a'),
    ]

    return config


def gcom_shared_object_config():
    from fab.dep_tree import by_type

    config = gcom_object_archive_config()
    config.label = 'gcom shared object'

    # don't pull the source again
    config.grab_config = None

    # compile with fPIC
    fc: CompileFortran = list(by_type(config.steps, CompileFortran))[0]
    fc.flags.common_flags.append('-fPIC')

    cc: CompileC = list(by_type(config.steps, CompileC))[0]
    cc.flags.common_flags.append('-fPIC')

    # link the object archive
    config.steps.append(LinkSharedObject(
        linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
        output_fpath='$output/libgcom.so'))

    return config


def main():
    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    # ignore this, it's not here
    config = gcom_object_archive_config()
    with time_logger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)
    with time_logger("extracting"):
        extract_will_do_this(config.file_filtering, config.workspace)

    #
    configs = [gcom_object_archive_config(), gcom_shared_object_config()]
    for config in configs:
        with time_logger("gcom build"):
            Build(config=config).run()


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


# class PathFilter(object):
#     def __init__(self, path_filters, include):
#         self.path_filters = path_filters
#         self.include = include
#
#     def check(self, path):
#         if any(i in str(path) for i in self.path_filters):
#             return self.include
#         return None


# def extract_will_do_this(path_filters, workspace):
#     source_folder = workspace / SOURCE_ROOT
#     build_tree = workspace / BUILD_SOURCE
#
#     # tuples to objects
#     path_filters = [PathFilter(*i) for i in path_filters]
#
#     for fpath in file_walk(source_folder):
#
#         include = True
#         for path_filter in path_filters:
#             res = path_filter.check(fpath)
#             if res is not None:
#                 include = res
#
#         # copy it to the build folder?
#         if include:
#             rel_path = fpath.relative_to(source_folder)
#             dest_path = build_tree / rel_path
#             # make sure the folder exists
#             if not dest_path.parent.exists():
#                 os.makedirs(dest_path.parent)
#             shutil.copy(fpath, dest_path)
#
#         # else:
#         #     print("excluding", fpath)


if __name__ == '__main__':
    main()

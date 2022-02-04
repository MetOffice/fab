#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.builder import Build
from fab.config import AddFlags, ConfigSketch
from fab.constants import SOURCE_ROOT, BUILD_SOURCE
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.preprocess import CPreProcessor, FortranPreProcessor
from fab.steps.walk_source import WalkSource
from fab.util import file_walk, time_logger


def gcom_common_config():
    project_name = 'gcom'
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

    grab_config = {
        ("gcom", "~/svn/gcom/trunk/build"),
    }

    extract_config = []

    return ConfigSketch(
        project_name=project_name,
        workspace=workspace,
        # use_multiprocessing=False,

        grab_config=grab_config,
        extract_config=extract_config,

        steps=[
            WalkSource(workspace / BUILD_SOURCE),  # template?
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
    )


def gcom_static_config():
    config = gcom_common_config()
    config.output_filename = 'libgcom.a'
    return config


# def gcom_shared_config():
#     config = gcom_common_config()
#     config.output_filename = 'libgcom.so'
#
#     # todo: probably nicer to make a new object and combine them
#     config.fc_flag_config.all_path_flags.append(AddFlags(add=['-fPIC']))
#     config.cc_flag_config.all_path_flags.append(AddFlags(add=['-fPIC']))
#
#     return config


def main():
    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    # config
    config = gcom_static_config()

    # Get source repos
    with time_logger("grabbing"):
        grab_will_do_this(config.grab_config, config.workspace)

    # Extract the files we want to build
    with time_logger("extracting"):
        extract_will_do_this(config.extract_config, config.workspace)

    my_fab = Build(config=config)

    with time_logger("gcom build"):
        my_fab.run()


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


class PathFilter(object):
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include = include

    def check(self, path):
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


def extract_will_do_this(path_filters, workspace):
    source_folder = workspace / SOURCE_ROOT
    build_tree = workspace / BUILD_SOURCE

    # tuples to objects
    path_filters = [PathFilter(*i) for i in path_filters]

    for fpath in file_walk(source_folder):

        include = True
        for path_filter in path_filters:
            res = path_filter.check(fpath)
            if res is not None:
                include = res

        # copy it to the build folder?
        if include:
            rel_path = fpath.relative_to(source_folder)
            dest_path = build_tree / rel_path
            # make sure the folder exists
            if not dest_path.parent.exists():
                os.makedirs(dest_path.parent)
            shutil.copy(fpath, dest_path)

        # else:
        #     print("excluding", fpath)


if __name__ == '__main__':
    main()

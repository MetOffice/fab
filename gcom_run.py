#!/usr/bin/env python

import os
import logging
import shutil
import sys

from pathlib import Path

from fab.config_sketch import PathFlags, FlagsConfig, ConfigSketch
from fab.constants import SOURCE_ROOT, BUILD_SOURCE

from fab.builder import Fab
from fab.util import file_walk, time_logger


def gcom_common_config():

    project_name = 'gcom'

    grab_config = {
        os.path.expanduser("~/svn/gcom/trunk/build"): "gcom",
    }

    extract_config = []

    cpp_flag_config = FlagsConfig()

    fpp_flag_config = FlagsConfig(
        path_flags=[
            PathFlags(add=['-I', '/gcom/include']),
            PathFlags(add=['-DGC_VERSION="7.6"']),
            PathFlags(add=['-DGC_BUILD_DATE="20220111"']),
            PathFlags(add=['-DGC_DESCRIP="dummy desrip"']),
            PathFlags(add=['-DPREC_64B', '-DMPILIB_32B']),
        ]
    )

    fc_flag_config = FlagsConfig()
    cc_flag_config = FlagsConfig(
        path_flags=[
            PathFlags(add=['-std=c99'])
        ]
    )

    return ConfigSketch(
        project_name=project_name,
        grab_config=grab_config,
        extract_config=extract_config,
        cpp_flag_config=cpp_flag_config,
        fpp_flag_config=fpp_flag_config,
        fc_flag_config=fc_flag_config,
        cc_flag_config=cc_flag_config,
        ld_flags=[
            # '-L', os.path.expanduser('~/.conda/envs/sci-fab/lib'),
        ],
        root_symbol=None,
        output_filename=None,
        unreferenced_dependencies=[],
    )


def gcom_static_config():
    config = gcom_common_config()
    config.output_filename = 'libgcom.a'
    return config


def gcom_shared_config():
    config = gcom_common_config()
    config.output_filename = 'libgcom.so'

    # todo: probably nicer to make a new object and combine them
    config.fc_flag_config.path_flags.append(PathFlags(add=['-fPIC']))
    config.cc_flag_config.path_flags.append(PathFlags(add=['-fPIC']))

    return config


def main():
    logger = logging.getLogger('fab')
    # logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    # config
    config_sketch = gcom_static_config()
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / config_sketch.project_name

    # Get source repos
    with time_logger("grabbing"):
        grab_will_do_this(config_sketch.grab_config, workspace)

    # Extract the files we want to build
    with time_logger("extracting"):
        extract_will_do_this(config_sketch.extract_config, workspace)


    my_fab = Fab(
        workspace=workspace,
        config=config_sketch,

        # fab behaviour
        n_procs=3,
        use_multiprocessing=False,
        debug_skip=True,
        # dump_source_tree=True
     )

    with time_logger("fab run"):
        my_fab.run()


def grab_will_do_this(src_paths, workspace):
    for src_path, label in src_paths.items():
        shutil.copytree(src_path, workspace / SOURCE_ROOT / label, dirs_exist_ok=True)


def extract_will_do_this(path_filters, workspace):
    source_folder = workspace / SOURCE_ROOT
    build_tree = workspace / BUILD_SOURCE

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

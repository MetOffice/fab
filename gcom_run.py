import os
import logging
import shutil
import sys
from collections import namedtuple

from pathlib import Path

from config_sketch import PathFlags, FlagsConfig, PathFilter
from fab.constants import SOURCE_ROOT, BUILD_SOURCE

from fab.builder import Fab, read_config
from fab.util import file_walk, time_logger


ConfigSketch = namedtuple(
    'ConfigSketch',
    ['project_name', 'grab_config', 'extract_config', 'cpp_flag_config', 'fpp_flag_config', 'fc_flag_config', 'cc_flag_config']
)


def gcom_config():
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
            PathFlags(add=['-DPREC_32B']),
        ]
    )

    fc_flag_config = FlagsConfig(
        path_flags=[
            PathFlags(add=['-fPIC'])
        ]
    )
    cc_flag_config = FlagsConfig(
        path_flags=[
            PathFlags(add=['-std=c99', '-fPIC'])
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
    )


def main():

    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)


    # config
    config_sketch = gcom_config()
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / config_sketch.project_name

    # # Get source repos
    # with time_logger("grabbing"):
    #     grab_will_do_this(config_sketch.grab_config, workspace)
    #
    # # Extract the files we want to build
    # with time_logger("extracting"):
    #     extract_will_do_this(config_sketch.extract_config, workspace)


    # fab build stuff
    config = read_config("gcom.config")
    settings = config['settings']

    my_fab = Fab(
        # fab behaviour
        n_procs=3,
        stop_on_error=True,
        use_multiprocessing=False,
        debug_skip=True,
        # dump_source_tree=True

        # build config
        workspace=workspace,
        target=settings['target'],
        exec_name=settings['exec-name'],
        cpp_flags=config_sketch.cpp_flag_config,
        fpp_flags=config_sketch.fpp_flag_config,
        fc_flags=config_sketch.fc_flag_config,
        cc_flags=config_sketch.cc_flag_config,
        ld_flags="",
        skip_files=config.skip_files,
        unreferenced_deps=config.unreferenced_deps,
        # include_paths=config.include_paths,  # todo: not clear if for pp or comp
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

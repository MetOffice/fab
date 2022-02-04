#!/usr/bin/env python

import logging
import os
import shutil
from pathlib import Path

from fab.builder import Build
from fab.constants import SOURCE_ROOT


def main():
    # config
    project_name = "jules"
    src_paths = {
        os.path.expanduser("~/svn/jules/trunk/src"): "src",
        os.path.expanduser("~/svn/jules/trunk/utils"): "utils",
    }

    #
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

    # TODO: This will be part of grab/extract
    # Copy all source into workspace
    for src_path, label in src_paths.items():
        shutil.copytree(src_path, workspace / SOURCE_ROOT / label, dirs_exist_ok=True)

    config = read_config("jules.config")
    settings = config['settings']
    flags = config['flags']

    my_fab = Build(workspace=workspace,
                   target=settings['target'],
                   exec_name=settings['exec-name'],
                   fpp_flags=flags['fpp-flags'],
                   fc_flags=flags['fc-flags'],
                   ld_flags=flags['ld-flags'],
                   n_procs=3,
                   stop_on_error=True,
                   skip_files=config.skip_files,
                   unreferenced_deps=config.unreferenced_deps,
                   # use_multiprocessing=False,
                   # debug_skip=True,
                   include_paths=config.include_paths)

    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    my_fab.run()


if __name__ == '__main__':
    main()

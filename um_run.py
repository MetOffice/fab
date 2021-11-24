#
# cli equivalent:
#   fab ~/svn/um/trunk/src um.config -w ~/git/fab/tmp-workspace-um --stop-on-error -vv
#
# optionally (default):
#   --nprocs 2
#
# cli also needs um.config:
#     [settings]
#     target = um
#     exec-name = um
#
#     [flags]
#     fpp-flags =
#     fc-flags =
#     ld-flags =
#
import os
import logging
# from argparse import ArgumentParser

from pathlib import Path
from typing import List

from fab.builder import Fab, read_config


def main():

    # argparser = ArgumentParser()
    # argparser.add_argument("um_path", required=False, default="~/svn/trunk")
    # args = argparser.parse_args()

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace-um"
    src_paths: List[Path] = [
        Path(os.path.expanduser('~/svn/um/trunk/src')),
        Path(os.path.expanduser('~/svn/um/trunk/utils')),
    ]

    config, skip_files = read_config("um.config")
    settings = config['settings']
    flags = config['flags']

    my_fab = Fab(workspace=workspace,
                 target=settings['target'],
                 exec_name=settings['exec-name'],
                 fpp_flags=flags['fpp-flags'],
                 fc_flags=flags['fc-flags'],
                 ld_flags=flags['ld-flags'],
                 n_procs=3,  # should be able to pass in 1, but it subtracts 1!
                 stop_on_error=True,
                 skip_files=skip_files,
                 skip_if_exists=True,
                 unreferenced_deps=settings['unreferenced-dependencies'].split(','))

    logger = logging.getLogger('fab')
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    my_fab.run(source_paths=src_paths)


if __name__ == '__main__':
    main()

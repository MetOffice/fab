#
# cli equivalent:
#   fab ~/svn/jules/trunk/src jules.config -w ~/git/fab/tmp-workspace-jules --stop-on-error -vv
#
# optionally (default):
#   --nprocs 2
#
# cli also needs jules.config:
#     [settings]
#     target = jules
#     exec-name = jules.exe
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
    # argparser.add_argument("jules_path", required=False, default="~/svn/trunk")
    # args = argparser.parse_args()

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace-jules"
    # todo: remove bblay
    # src_paths: List[Path] = [
    #     Path(os.path.expanduser('~/svn/jules/trunk/src')),
    #     Path(os.path.expanduser('~/svn/jules/trunk/utils')),
    # ]

    config = read_config("jules.config")
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
                 skip_files=config.skip_files,
                 unreferenced_deps=config.unreferenced_deps,
                 debug_skip=True)

    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    my_fab.run(source_paths=config.src_paths)


if __name__ == '__main__':
    main()

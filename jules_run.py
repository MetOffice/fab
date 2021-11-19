#
# cli equivalent:
#   fab /home/h02/bblay/svn/trunk/src jules.config -w /home/h02/bblay/git/fab/tmp-workspace --stop-on-error -vv
#
# optionally (default):
#   --nprocs 2
#
# cli also needs jules.config:
#     [settings]
#     target = jules
#     exec-name = output
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

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace"
    src_paths: List[Path] = [
        Path('/home/h02/bblay/svn/trunk/src'),
        Path('/home/h02/bblay/svn/trunk/utils'),
    ]

    # src_paths: List[Path] = [
    #     Path(args.jules_path) / 'src',
    #     Path(args.jules_path) / 'utils',
    # ]

    config, skip_files = read_config("jules.config")
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

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

from pathlib import Path

from fab.builder import Fab, read_config


def main():

    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace-um"

    config = read_config("um.config")
    settings = config['settings']
    flags = config['flags']

    my_fab = Fab(workspace=workspace,
                 target=settings['target'],
                 exec_name=settings['exec-name'],
                 fpp_flags=flags['fpp-flags'],
                 fc_flags=flags['fc-flags'],
                 ld_flags=flags['ld-flags'],
                 n_procs=3,
                 # n_procs=1,
                 stop_on_error=True,
                 skip_files=config.skip_files,
                 unreferenced_deps=config.unreferenced_deps,
                 # use_multiprocessing=False
                 debug_skip=True,
                 include_paths=config.include_paths)

    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    my_fab.run(source_paths=config.src_paths)


if __name__ == '__main__':
    main()

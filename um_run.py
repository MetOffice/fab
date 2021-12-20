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
import shutil

from pathlib import Path

from fab.constants import SOURCE_ROOT

from fab.builder import Fab, read_config
from fab.util import file_walk, time_logger


def main():

    # config
    project_name = "um"
    src_paths = {
        os.path.expanduser("~/svn/um/trunk/src"): "um",
        os.path.expanduser("~/svn/socrates/trunk/src"): "socrates",
    }

    #
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

    simulate_grab = False
    # simulate_grab = True


    # TODO: This will be part of grab/extract
    if simulate_grab:
        # Copy all source into workspace
        for src_path, label in src_paths.items():
            shutil.copytree(src_path, workspace / SOURCE_ROOT / label, dirs_exist_ok=True)

        # shum partial
        shum_excl = ["common/src/shumlib_version.c", "Makefile"]
        shum_incl = [
            "shum_wgdos_packing/src",
            "shum_string_conv/src",
            "shum_latlon_eq_grids/src",
            "shum_horizontal_field_interp/src",
            "shum_spiral_search/src",
            "shum_constants/src",
            "shum_thread_utils/src",
            "shum_data_conv/src",
            "shum_number_tools/src",
            "shum_byteswap/src",
            "common/src",
        ]

        shum_src = Path(os.path.expanduser("~/svn/shumlib/trunk"))
        for fpath in file_walk(shum_src):
            if any([i in str(fpath) for i in shum_excl]):
                continue
            if any([i in str(fpath) for i in shum_incl]):
                rel_path = fpath.relative_to(shum_src)
                output_fpath = workspace / SOURCE_ROOT / "shumlib" / rel_path
                if not output_fpath.parent.exists():
                    output_fpath.parent.mkdir(parents=True)
                shutil.copy(fpath, output_fpath)

    ### END OF DONE-BYGRAB STUFF





    # fab build stuff
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
                 stop_on_error=True,
                 skip_files=config.skip_files,
                 unreferenced_deps=config.unreferenced_deps,
                 # use_multiprocessing=False,
                 debug_skip=True,
                 include_paths=config.include_paths)

    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    with time_logger("fab run"):
        my_fab.run()


if __name__ == '__main__':
    main()

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

from config_sketch import PathFlags, FlagsConfig
from fab.constants import SOURCE_ROOT

from fab.builder import Fab, read_config
from fab.util import file_walk, time_logger


def get_um_flag_config(workspace):

    # fpp
    fpp_flag_config = FlagsConfig(
        # todo: bundle (some of) these with the 'cpp' definintion?
        path_flags=[PathFlags(add=['-DUM_JULES'])])

    # fc
    # todo: bundle these with the gfortran definition
    um_fc_flags = PathFlags()

    shum_fc_flags = PathFlags(
        path_filter="tmp-workspace/um/output/shumlib/",
        # add=['-std=f2018']
    )

    fc_flag_config = FlagsConfig(
        path_flags=[um_fc_flags, shum_fc_flags])

    return fpp_flag_config, fc_flag_config


def main():

    # config
    project_name = "um"
    src_paths = {
        os.path.expanduser("~/svn/um/trunk/src"): "um",
        os.path.expanduser("~/svn/socrates/trunk/src"): "socrates",
    }

    #
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

    # Copy all source into workspace
    # grab_will_do_this(src_paths, workspace, logger)

    ### END OF DONE BY GRAB STUFF

    fpp_flag_config, fc_flag_config = get_um_flag_config(workspace)


# hierarchy of config
#
# site (sys admin)
# project (source code)
# overrides
# blocked overrides
#
# what ought to inherit from env
# num cores in submit script, mem
# batch manager assigns resources
# project board in about amonth




    # fab build stuff
    config = read_config("um.config")
    settings = config['settings']
    # flags = config['flags']

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
        fpp_flags=fpp_flag_config,
        fc_flags=fc_flag_config,
        ld_flags="",
        skip_files=config.skip_files,
        unreferenced_deps=config.unreferenced_deps,
        include_paths=config.include_paths,  # todo: not clear if for pp or comp
     )

    logger = logging.getLogger('fab')
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    with time_logger("fab run"):
        my_fab.run()


def grab_will_do_this(src_paths, workspace, logger):
    logger.info("faking grab")
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


if __name__ == '__main__':
    main()

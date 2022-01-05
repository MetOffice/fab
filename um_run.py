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

    ### END OF DONE BY GRAB STUFF











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






    class Thing(object):
        def __init__(self, fpp_flags, fc_flags):
            self.fpp_flags = fpp_flags
            self.fc_flags = fc_flags

    foo = Thing(
        fpp_flags=["-DUM_JULES"],
        fc_flags=[],
    )

    shum = OtherThing(
        pattern="/home/h02/bblay/git/fab/tmp-workspace/um/output/shumlib",
        action=lambda foo: foo.fc_flags.extend(["-std=2018"])
    )

    if analysed_file.fpath.startswith(shum.pattern):
        shum.action(foo)




    # todo: replace -O2 with -O1

    foo = Thing(
        fpp_flags=[],
        fc_flags=["-O2", "-foo"],
    )

    def set_fc_flag(foo, flag_name, flag_val):
        # remove existing flag_name
        pass

        # set new
        foo.fc_flags.append(f"-{flag_name}={flag_val}")

    shum = OtherThing(
        pattern="/home/h02/bblay/git/fab/tmp-workspace/um/output/shumlib",
        action=lambda foo: set_fc_flag(foo, "O", 1)
    )

    if analysed_file.fpath.startswith(shum.pattern):
        shum.action(foo)





    # complete replace
    fc_flags = ["-foo=bar"]         ->          fc_flags = ["-brain=hurts"]

    # form from existing parts
    fc_flags = thing1 + thing2

    # replace single flag
    action = set(fc_flags, "-O", "1")           -> ["-foo=bar", "-O2"]  -> ["-foo=bar", "-O1"]
    action = set(fc_flags, "-std", "f2018")     -> ["-foo=bar", "-std=gnu"] -> ["-foo=bar", "-std=2018"]















    # fab build stuff
    config = read_config("um.config")
    settings = config['settings']
    flags = config['flags']

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
        fpp_flags=flags['fpp-flags'],
        fc_flags=flags['fc-flags'],
        ld_flags=flags['ld-flags'],
        skip_files=config.skip_files,
        unreferenced_deps=config.unreferenced_deps,
        include_paths=config.include_paths,  # todo: not clear if for pp or comp
     )

    logger = logging.getLogger('fab')
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)

    with time_logger("fab run"):
        my_fab.run()


if __name__ == '__main__':
    main()

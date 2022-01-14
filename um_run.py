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
import sys
import warnings
from collections import namedtuple

from pathlib import Path

from fab.dep_tree import AnalysedFile

from fab.config_sketch import PathFlags, FlagsConfig, PathFilter, ConfigSketch
from fab.constants import SOURCE_ROOT, BUILD_SOURCE, BUILD_OUTPUT

from fab.builder import Fab
from fab.util import file_walk, time_logger, case_insensitive_replace


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


def um_atmos_safe_config():

    project_name = 'um_atmos_safe'

    # todo: docstring about relative and absolute (=output) include paths
    #       this is quite tightly coupled to the preprocessor


    # grab
    grab_config = {
        os.path.expanduser("~/svn/um/trunk/src"): "um",
        os.path.expanduser("~/svn/jules/trunk/src"): "jules",
        os.path.expanduser("~/svn/socrates/trunk/src"): "socrates",
        os.path.expanduser("~/svn/shumlib/trunk"): "shumlib",
        os.path.expanduser("~/svn/casim/src"): "casim",
    }

    # extract
    extract_config = [
        PathFilter(['/um/utility/'], include=False),
        PathFilter(['/um/utility/qxreconf/'], include=True),

        PathFilter(['/um/atmosphere/convection/comorph/interface/'], include=False),
        PathFilter(['/um/atmosphere/convection/comorph/interface/um/'], include=True),

        PathFilter(['/um/atmosphere/convection/comorph/unit_tests/'], include=False),

        PathFilter(['/um/scm/'], include=False),
        PathFilter(['/um/scm/stub/',
                    '/um/scm/modules/s_scmop_mod.F90',
                    '/um/scm/modules/scmoptype_defn.F90'],
                   include=True),

        PathFilter(['/jules/'], include=False),
        PathFilter(['/jules/control/shared/',
                    '/jules/control/um/',
                    '/jules/initialisation/shared/',
                    '/jules/initialisation/um/',
                    '/jules/params/um/',
                    '/jules/science/',
                    '/jules/util/shared/',
                    ], include=True),

        PathFilter(['/socrates/'], include=False),
        PathFilter(['/socrates/nlte/',
                    '/socrates/radiance_core/'
                    ], include=True),

        # the shummlib config in fcm config doesn't seem to do anything, perhaps there used to be extra files we needed to exclude
        PathFilter(['/shumlib/'], include=False),
        PathFilter(['/shumlib/shum_wgdos_packing/src',
                    '/shumlib/shum_string_conv/src',
                    '/shumlib/shum_latlon_eq_grids/src',
                    '/shumlib/shum_horizontal_field_interp/src',
                    '/shumlib/shum_spiral_search/src',
                    '/shumlib/shum_constants/src',
                    '/shumlib/shum_thread_utils/src',
                    '/shumlib/shum_data_conv/src',
                    '/shumlib/shum_number_tools/src',
                    '/shumlib/shum_byteswap/src',
                    '/shumlib/common/src',
                    ], include=True),
        PathFilter(['/shumlib/common/src/shumlib_version.c'], include=False),

        PathFilter(['/casim/mphys_die.F90',
                    '/casim/mphys_casim.F90',
                    ], include=False),

        PathFilter(['.xml'], include=False),
        PathFilter(['.sh'], include=False),
    ]

    # fpp
    cpp_flag_config = FlagsConfig(
        # todo: bundle (some of) these with the 'cpp' definintion?
        path_flags=[
            PathFlags(path_filter=f"tmp-workspace/{project_name}/{BUILD_SOURCE}/um/",  # todo: calc up to the output bit
                      add=['-I', '/um/include/other', '-I', '/shumlib/common/src', '-I', '/shumlib/shum_thread_utils/src']),
            PathFlags(path_filter=f"tmp-workspace/{project_name}/{BUILD_SOURCE}/shumlib/",
                      add=['-I', '/shumlib/common/src', '-I', '/shumlib/shum_thread_utils/src']),
        ])

    fpp_flag_config = FlagsConfig(
        # todo: bundle (some of) these with the 'cpp' definintion?
        # todo: remove the ease of mistaking BUILD_SOURCE with BUILD_OUTPUT - pp knows it's input -> output
        path_flags=[
            PathFlags(path_filter=f"tmp-workspace/{project_name}/{BUILD_SOURCE}/jules/", add=['-DUM_JULES']),
            PathFlags(path_filter=f"tmp-workspace/{project_name}/{BUILD_SOURCE}/um/", add=['-I', 'include']),
            PathFlags(path_filter=f"tmp-workspace/{project_name}/{BUILD_SOURCE}/um/control/timer/", add=['-DC97_3A']),
        ])

    # todo: bundle these with the gfortran definition
    fc_flag_config = FlagsConfig(
        path_flags=[
            PathFlags(add=['-fdefault-integer-8', '-fdefault-real-8', '-fdefault-double-8']),
            PathFlags(
                path_filter=f"tmp-workspace/{project_name}/{BUILD_OUTPUT}/um/",
                add=['-I', os.path.expanduser("~/git/fab/tmp-workspace/gcom/build_output")]),
            PathFlags(add=['-fallow-argument-mismatch'])  # required from gfortran 10 - discuss
        ]
    )

    cc_flag_config = FlagsConfig()

    special_measure_analysis_results = [
        AnalysedFile(
            fpath=Path(os.path.expanduser("~/git/fab/tmp-workspace/um_atmos_safe/build_output/casim/lookup.f90")),
            file_hash=None,
            symbol_defs=['lookup'],
            symbol_deps=['mphys_die', 'variable_precision', 'mphys_switches', 'mphys_parameters', 'special',
                         'passive_fields', 'casim_moments_mod', 'yomhook', 'parkind1'],
            file_deps=[],
            mo_commented_file_deps=[]),
    ]

    return ConfigSketch(
        project_name=project_name,
        grab_config=grab_config,
        extract_config=extract_config,
        cpp_flag_config=cpp_flag_config,
        fpp_flag_config=fpp_flag_config,
        fc_flag_config=fc_flag_config,
        cc_flag_config=cc_flag_config,
        ld_flags=[],
        root_symbol='um_main',
        output_filename=None,
        unreferenced_dependencies=[],
        special_measure_analysis_results=special_measure_analysis_results,
    )


def main():

    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    # config
    config_sketch = um_atmos_safe_config()
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / config_sketch.project_name

    # Get source repos
    # with time_logger("grabbing"):
    #     grab_will_do_this(config_sketch.grab_config, workspace)

    # Extract the files we want to build
    # with time_logger("extracting"):
    #     extract_will_do_this(config_sketch.extract_config, workspace)

    my_fab = Fab(
        workspace=workspace,
        config=config_sketch,

        # fab behaviour
        n_procs=3,
        # use_multiprocessing=False,
        debug_skip=True,
        # dump_source_tree=True
     )

    with time_logger("fab run"):
        my_fab.run()


def grab_will_do_this(src_paths, workspace):  #, logger):
    #logger.info("faking grab")
    for src_path, label in src_paths.items():
        shutil.copytree(
            src_path,
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )

    # # todo: move into config
    # # shum partial
    # shum_excl = ["common/src/shumlib_version.c", "Makefile"]
    # shum_incl = [
    #     "shum_wgdos_packing/src",
    #     "shum_string_conv/src",
    #     "shum_latlon_eq_grids/src",
    #     "shum_horizontal_field_interp/src",
    #     "shum_spiral_search/src",
    #     "shum_constants/src",
    #     "shum_thread_utils/src",
    #     "shum_data_conv/src",
    #     "shum_number_tools/src",
    #     "shum_byteswap/src",
    #     "common/src",
    # ]
    # shum_src = Path(os.path.expanduser("~/svn/shumlib/trunk"))
    # for fpath in file_walk(shum_src):
    #     if any([i in str(fpath) for i in shum_excl]):
    #         continue
    #     if any([i in str(fpath) for i in shum_incl]):
    #         rel_path = fpath.relative_to(shum_src)
    #         output_fpath = workspace / SOURCE_ROOT / "shumlib" / rel_path
    #         if not output_fpath.parent.exists():
    #             output_fpath.parent.mkdir(parents=True)
    #         shutil.copy(fpath, output_fpath)


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

    # SPECIAL CODE FIXES!!! NEED ADDRESSING
    special_code_fixes()


def special_code_fixes():

    def replace_in_file(inpath, outpath, find, replace):
        open(os.path.expanduser(outpath), "wt").write(
            case_insensitive_replace(
                in_str=open(os.path.expanduser(inpath), "rt").read(),
                find=find, replace_with=replace))

    warnings.warn("SPECIAL MEASURE for io_configuration_mod.F90: fparser2 misunderstands the variable 'NameListFile'")
    replace_in_file('~/git/fab/tmp-workspace/um_atmos_safe/source/um/io_services/common/io_configuration_mod.F90',
                    '~/git/fab/tmp-workspace/um_atmos_safe/build_source/um/io_services/common/io_configuration_mod.F90',
                    'NameListFile', 'FabNameListFile')

    warnings.warn("SPECIAL MEASURE for um_config.F90: fparser2 misunderstands the variable 'NameListFile'")
    replace_in_file('~/git/fab/tmp-workspace/um_atmos_safe/source/um/control/top_level/um_config.F90',
                    '~/git/fab/tmp-workspace/um_atmos_safe/build_source/um/control/top_level/um_config.F90',
                    'NameListFile', 'FabNameListFile')


if __name__ == '__main__':
    main()

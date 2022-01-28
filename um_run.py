#!/usr/bin/env python

# Note: we need this to run the exe
#   export LD_LIBRARY_PATH=~/.conda/envs/sci-fab/lib:$LD_LIBRARY_PATH

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

import logging
import os
import shutil
import warnings
from pathlib import Path

from fab.steps import Step

from fab.builder import Build
from fab.config import AddPathFlags, FlagsConfig, PathFilter, ConfigSketch
from fab.constants import SOURCE_ROOT, BUILD_SOURCE, BUILD_OUTPUT
from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import FortranPreProcessor, CPreProcessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.walk_source import WalkSource
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


def set_workspace(workspace):
    Step.workspace = workspace  # todo: do we need this in there?
    AddPathFlags.workspace = workspace


def um_atmos_safe_config():
    project_name = 'um_atmos_safe'
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name
    set_workspace(workspace)

    Step.use_multiprocessing = False
    # Step.debug_skip = True

    grab_config = {
        ("um", "~/svn/um/trunk/src"),
        ("jules", "~/svn/jules/trunk/src"),
        ("socrates", "~/svn/socrates/trunk/src"),
        ("shumlib", "~/svn/shumlib/trunk"),
        ("casim", "~/svn/casim/src"),
    }

    extract_config = [
        (['/um/utility/'], False),
        (['/um/utility/qxreconf/'], True),

        (['/um/atmosphere/convection/comorph/interface/'], False),
        (['/um/atmosphere/convection/comorph/interface/um/'], True),

        (['/um/atmosphere/convection/comorph/unit_tests/'], False),

        (['/um/scm/'], False),
        (['/um/scm/stub/',
          '/um/scm/modules/s_scmop_mod.F90',
          '/um/scm/modules/scmoptype_defn.F90'], True),

        (['/jules/'], False),
        (['/jules/control/shared/',
          '/jules/control/um/',
          '/jules/initialisation/shared/',
          '/jules/initialisation/um/',
          '/jules/params/um/',
          '/jules/science/',
          '/jules/util/shared/'], True),

        (['/socrates/'], False),
        (['/socrates/nlte/',
          '/socrates/radiance_core/'], True),

        # the shummlib config in fcm config doesn't seem to do anything,
        # perhaps there used to be extra files we needed to exclude
        (['/shumlib/'], False),
        (['/shumlib/shum_wgdos_packing/src',
          '/shumlib/shum_string_conv/src',
          '/shumlib/shum_latlon_eq_grids/src',
          '/shumlib/shum_horizontal_field_interp/src',
          '/shumlib/shum_spiral_search/src',
          '/shumlib/shum_constants/src',
          '/shumlib/shum_thread_utils/src',
          '/shumlib/shum_data_conv/src',
          '/shumlib/shum_number_tools/src',
          '/shumlib/shum_byteswap/src',
          '/shumlib/common/src'], True),
        (['/shumlib/common/src/shumlib_version.c'], False),

        (['/casim/mphys_die.F90',
          '/casim/mphys_casim.F90',], False),

        (['.xml'], False),
        (['.sh'], False),
    ]

    c_preprocessor = CPreProcessor(
        preprocessor='cpp',
        path_flags=[
            ("$source/um/*",
             ['-I', '$source/um/include/other',  # todo: explain, relative to which root?
              '-I', '$source/shumlib/common/src',
              '-I', '$source/shumlib/shum_thread_utils/src']),

            ("$source/shumlib/*",
             ['-I', '$source/shumlib/common/src',
              '-I', '$source/shumlib/shum_thread_utils/src']),

            # todo: just 3 folders use this
            ("$source/um/*",
             ['-DC95_2A',
              '-I', '$source/shumlib/shum_byteswap/src']),
        ],
    )

    # todo: explain fnmatch
    fortran_preprocessor = FortranPreProcessor(
        preprocessor='cpp',
        common_flags=['-traditional-cpp', '-P'],
        path_flags=[
            ("$source/jules/*", ['-DUM_JULES']),
            ("$source/um/*", ['-I', '$relative/include']),

            # coupling defines
            ("$source/um/control/timer/*", ['-DC97_3A']),
            ("$source/um/io_services/client/stash/*", ['-DC96_1C']),
        ],
    )

    analyser = Analyse(
        root_symbol='um_main',
        unreferenced_deps=None,

        # fparser2 fails to parse this file, but it does compile.
        special_measure_analysis_results=[
            AnalysedFile(
                fpath=Path(os.path.expanduser("~/git/fab/tmp-workspace/um_atmos_safe/build_output/casim/lookup.f90")),
                file_hash=None,
                symbol_defs=['lookup'],
                symbol_deps=['mphys_die', 'variable_precision', 'mphys_switches', 'mphys_parameters', 'special',
                             'passive_fields', 'casim_moments_mod', 'yomhook', 'parkind1'],
                file_deps=[],
                mo_commented_file_deps=[]),
        ]
    )

    c_compiler = CompileC(compiler=['gcc', '-c', '-std=c99'], flags=FlagsConfig(), workspace=workspace)

    fortran_compiler = CompileFortran(
        compiler=[
            os.path.expanduser('~/.conda/envs/sci-fab/bin/gfortran'),
            '-c',
            '-J', '$output',  # .mod file output and include folder
        ],
        common_flags=['-fdefault-integer-8', '-fdefault-real-8', '-fdefault-double-8'],
        path_flags=[

            # mpl include - todo: just add this for everything?
            (f"$output/um/", ['-I', "$output"]),
            (f"$output/jules/", ['-I', "$output"]),

            # TODO: REVIEWERS, SHOULD WE NEED THESE?
            # a not recommended flag?
            # todo: allow a list of filters?
            ('hardware_topology_mod.f90', ['-fallow-argument-mismatch']),
            ('setup_spectra_mod.f90', ['-fallow-argument-mismatch']),
            ('mcica_mod.f90', ['-fallow-argument-mismatch']),
            ('ios_comms.f90', ['-fallow-argument-mismatch']),
            ('ios_client_queue.f90', ['-fallow-argument-mismatch']),
            ('fastjx_specs.f90', ['-fallow-argument-mismatch']),
            ('history_mod.f90', ['-fallow-argument-mismatch']),
            ('lustre_control_mod.f90', ['-fallow-argument-mismatch']),
            ('imbnd_hill_mod.f90', ['-fallow-argument-mismatch']),
            ('io_configuration_mod.f90', ['-fallow-argument-mismatch']),
            ('nlstcall_nc_namelist_mod.f90', ['-fallow-argument-mismatch']),
            ('nlstcall_pp_namelist_mod.f90', ['-fallow-argument-mismatch']),
            ('ios.f90', ['-fallow-argument-mismatch']),
            ('regrid_alloc_calc_mod.f90', ['-fallow-argument-mismatch']),
            ('halo_exchange_ddt_mod.f90', ['-fallow-argument-mismatch']),
            ('halo_exchange_mpi_mod.f90', ['-fallow-argument-mismatch']),
            ('halo_exchange_os_mod.f90', ['-fallow-argument-mismatch']),
            ('mg_field_norm.f90', ['-fallow-argument-mismatch']),
            ('rdbasis.f90', ['-fallow-argument-mismatch']),
            ('io.f90', ['-fallow-argument-mismatch']),
            ('ppxlook_mod.f90', ['-fallow-argument-mismatch']),
            ('read_land_sea.f90', ['-fallow-argument-mismatch']),
            ('diagopr.f90', ['-fallow-argument-mismatch']),
            ('eg_bi_linear_h.f90', ['-fallow-argument-mismatch']),
            ('glomap_clim_netcdf_io_mod.f90', ['-fallow-argument-mismatch']),
            ('emiss_io_mod.f90', ['-fallow-argument-mismatch']),
            ('ios_stash_server.f90', ['-fallow-argument-mismatch']),
            ('io_server_listener.f90', ['-fallow-argument-mismatch']),
            ('acumps.f90', ['-fallow-argument-mismatch']),
            ('num_obs.f90', ['-fallow-argument-mismatch']),
            ('io_server_writer.f90', ['-fallow-argument-mismatch']),
            ('routedbl_mod.f90', ['-fallow-argument-mismatch']),
            ('ios_init.f90', ['-fallow-argument-mismatch']),
            ('eg_sl_helmholtz_inc.f90', ['-fallow-argument-mismatch']),
            ('ukca_scenario_rcp_mod.f90', ['-fallow-argument-mismatch']),
        ]
    )

    linker = LinkExe(
        # linker='gcc',
        linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
        flags=[
            '-lc', '-lgfortran', '-L', '~/.conda/envs/sci-fab/lib',
            '-L', os.path.expanduser('~/git/fab/tmp-workspace/gcom'), '-l', 'gcom'
        ],
        output_fpath='um_atmos.exe')

    return ConfigSketch(
        project_name=project_name,
        workspace=workspace,

        grab_config=grab_config,
        extract_config=extract_config,

        steps=[
            WalkSource(build_source=workspace / BUILD_SOURCE),
            RootIncFiles(build_source=workspace / BUILD_SOURCE),
            c_preprocessor,
            fortran_preprocessor,
            analyser,
            c_compiler,
            fortran_compiler,
            linker,
        ],

    )


def main():
    logger = logging.getLogger('fab')
    logger.setLevel(logging.INFO)

    # config
    config_sketch = um_atmos_safe_config()

    # Get source repos
    # with time_logger("grabbing"):
    #     grab_will_do_this(config_sketch.grab_config, workspace)

    # Extract the files we want to build
    # with time_logger("extracting"):
    #     extract_will_do_this(config_sketch.extract_config, workspace)

    builder = Build(config=config_sketch)

    with time_logger("fab run"):
        builder.run()


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


# def extract_will_do_this(path_filters, workspace):
#     source_folder = workspace / SOURCE_ROOT
#     build_tree = workspace / BUILD_SOURCE
#
#     for fpath in file_walk(source_folder):
#
#         include = True
#         for path_filter in path_filters:
#             res = path_filter.check(fpath)
#             if res is not None:
#                 include = res
#
#         # copy it to the build folder?
#         if include:
#             rel_path = fpath.relative_to(source_folder)
#             dest_path = build_tree / rel_path
#             # make sure the folder exists
#             if not dest_path.parent.exists():
#                 os.makedirs(dest_path.parent)
#             shutil.copy(fpath, dest_path)
#
#         # else:
#         #     print("excluding", fpath)
#
#     # SPECIAL CODE FIXES!!! NEED ADDRESSING
#     special_code_fixes()

def extract_will_do_this(path_filters, workspace):
    source_folder = workspace / SOURCE_ROOT
    build_tree = workspace / BUILD_SOURCE

    # tuples to objects
    path_filters = [PathFilter(*i) for i in path_filters]

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

#!/usr/bin/env python

# Note: we need this to run the exe
#   export LD_LIBRARY_PATH=~/.conda/envs/sci-fab/lib:$LD_LIBRARY_PATH

import logging
import os
import shutil
import warnings
from pathlib import Path

from fab.steps import Step

from fab.builder import Build
from fab.config import AddFlags, Config
from fab.constants import SOURCE_ROOT
from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import FortranPreProcessor, CPreProcessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.walk_source import GetSourceFiles
from fab.util import time_logger, case_insensitive_replace, Artefact


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


def um_atmos_safe_config():
    project_name = 'um_atmos_safe'
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

    # todo: make grab a step?
    grab_config = {
        ("um", "~/svn/um/trunk/src"),
        ("jules", "~/svn/jules/trunk/src"),
        ("socrates", "~/svn/socrates/trunk/src"),
        ("shumlib", "~/svn/shumlib/trunk"),
        ("casim", "~/svn/casim/src"),
    }

    file_filtering = [
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
          '/casim/mphys_casim.F90', ], False),

        (['.xml'], False),
        (['.sh'], False),
    ]

    return Config(
        label=project_name,
        workspace=workspace,

        # run params
        # use_multiprocessing=False,
        debug_skip=True,

        # source config - this will not be part of build, we have existing code to look at for this
        grab_config=grab_config,

        # build steps
        steps=[

            MyCustomCodeFixes(name="my custom code fixes"),

            GetSourceFiles(source_root=workspace / SOURCE_ROOT, file_filtering=file_filtering),  # template?

            RootIncFiles(workspace / SOURCE_ROOT),

            CPragmaInjector(),

            CPreProcessor(
                source=Artefact('pragmad_c'),
                preprocessor='cpp',
                path_flags=[
                    # todo: this is a bit "codey" - can we safely give longer strings and split later?
                    AddFlags(match="$source/um/*", flags=[
                        '-I', '$source/um/include/other',
                        '-I', '$source/shumlib/common/src',
                        '-I', '$source/shumlib/shum_thread_utils/src']),

                    AddFlags(match="$source/shumlib/*", flags=[
                        '-I', '$source/shumlib/common/src',
                        '-I', '$source/shumlib/shum_thread_utils/src']),

                    # todo: just 3 folders use this
                    AddFlags("$source/um/*", ['-DC95_2A', '-I', '$source/shumlib/shum_byteswap/src']),
                ],
            ),

            # todo: explain fnmatch
            FortranPreProcessor(
                preprocessor='cpp',
                common_flags=['-traditional-cpp', '-P'],
                path_flags=[
                    AddFlags("$source/jules/*", ['-DUM_JULES']),
                    AddFlags("$source/um/*", ['-I', '$relative/include']),

                    # coupling defines
                    AddFlags("$source/um/control/timer/*", ['-DC97_3A']),
                    AddFlags("$source/um/io_services/client/stash/*", ['-DC96_1C']),
                ],
            ),

            Analyse(
                root_symbol='um_main',
                unreferenced_deps=None,

                # fparser2 fails to parse this file, but it does compile.
                special_measure_analysis_results=[
                    AnalysedFile(
                        fpath=Path(
                            os.path.expanduser("~/git/fab/tmp-workspace/um_atmos_safe/build_output/casim/lookup.f90")),
                        file_hash=None,
                        symbol_defs=['lookup'],
                        symbol_deps=['mphys_die', 'variable_precision', 'mphys_switches', 'mphys_parameters', 'special',
                                     'passive_fields', 'casim_moments_mod', 'yomhook', 'parkind1'],
                        file_deps=[],
                        mo_commented_file_deps=[]),
                ]
            ),

            CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),

            CompileFortran(
                compiler=os.path.expanduser('~/.conda/envs/sci-fab/bin/gfortran'),
                common_flags=[
                    '-fdefault-integer-8', '-fdefault-real-8', '-fdefault-double-8',
                    '-c',
                    '-J', '$output',  # .mod file output and include folder
                ],

                path_flags=[
                    # mpl include - todo: just add this for everything?
                    AddFlags("$output/um/*", ['-I', os.path.expanduser("~/git/fab/tmp-workspace/gcom/build_output")]),
                    AddFlags("$output/jules/*",
                             ['-I', os.path.expanduser("~/git/fab/tmp-workspace/gcom/build_output")]),

                    # todo: allow multiple filters per instance?
                    *[AddFlags(*i) for i in ALLOW_MISMATCH_FLAGS]
                ]
            ),

            # todo: ArchiveObjects(),

            #
            LinkExe(
                # linker='gcc',
                linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
                flags=[
                    '-lc', '-lgfortran', '-L', '~/.conda/envs/sci-fab/lib',
                    '-L', os.path.expanduser('~/git/fab/tmp-workspace/gcom/build_output'), '-l', 'gcom'
                ],
                output_fpath='$output/../um_atmos.exe')
        ],

    )


# TODO: REVIEWERS, SHOULD WE NEED THESE?
# a not recommended flag?
# todo: allow a list of filters?
ALLOW_MISMATCH_FLAGS = [
    ('*/hardware_topology_mod.f90', ['-fallow-argument-mismatch']),
    ('*/setup_spectra_mod.f90', ['-fallow-argument-mismatch']),
    ('*/mcica_mod.f90', ['-fallow-argument-mismatch']),
    ('*/ios_comms.f90', ['-fallow-argument-mismatch']),
    ('*/ios_client_queue.f90', ['-fallow-argument-mismatch']),
    ('*/fastjx_specs.f90', ['-fallow-argument-mismatch']),
    ('*/history_mod.f90', ['-fallow-argument-mismatch']),
    ('*/lustre_control_mod.f90', ['-fallow-argument-mismatch']),
    ('*/imbnd_hill_mod.f90', ['-fallow-argument-mismatch']),
    ('*/io_configuration_mod.f90', ['-fallow-argument-mismatch']),
    ('*/nlstcall_nc_namelist_mod.f90', ['-fallow-argument-mismatch']),
    ('*/nlstcall_pp_namelist_mod.f90', ['-fallow-argument-mismatch']),
    ('*/ios.f90', ['-fallow-argument-mismatch']),
    ('*/regrid_alloc_calc_mod.f90', ['-fallow-argument-mismatch']),
    ('*/halo_exchange_ddt_mod.f90', ['-fallow-argument-mismatch']),
    ('*/halo_exchange_mpi_mod.f90', ['-fallow-argument-mismatch']),
    ('*/halo_exchange_os_mod.f90', ['-fallow-argument-mismatch']),
    ('*/mg_field_norm.f90', ['-fallow-argument-mismatch']),
    ('*/rdbasis.f90', ['-fallow-argument-mismatch']),
    ('*/io.f90', ['-fallow-argument-mismatch']),
    ('*/ppxlook_mod.f90', ['-fallow-argument-mismatch']),
    ('*/read_land_sea.f90', ['-fallow-argument-mismatch']),
    ('*/diagopr.f90', ['-fallow-argument-mismatch']),
    ('*/eg_bi_linear_h.f90', ['-fallow-argument-mismatch']),
    ('*/glomap_clim_netcdf_io_mod.f90', ['-fallow-argument-mismatch']),
    ('*/emiss_io_mod.f90', ['-fallow-argument-mismatch']),
    ('*/ios_stash_server.f90', ['-fallow-argument-mismatch']),
    ('*/io_server_listener.f90', ['-fallow-argument-mismatch']),
    ('*/acumps.f90', ['-fallow-argument-mismatch']),
    ('*/num_obs.f90', ['-fallow-argument-mismatch']),
    ('*/io_server_writer.f90', ['-fallow-argument-mismatch']),
    ('*/routedbl_mod.f90', ['-fallow-argument-mismatch']),
    ('*/ios_init.f90', ['-fallow-argument-mismatch']),
    ('*/eg_sl_helmholtz_inc.f90', ['-fallow-argument-mismatch']),
    ('*/ukca_scenario_rcp_mod.f90', ['-fallow-argument-mismatch']),
]


def main():
    logger = logging.getLogger('fab')
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)

    # config
    config = um_atmos_safe_config()

    # # Get source repos
    # with time_logger("grabbing"):
    #     grab_will_do_this(config.grab_config, config_sketch.workspace)

    builder = Build(config=config)

    with time_logger("um build"):
        builder.run()


#
# helper stuff to eventually throw away below here #
#


def grab_will_do_this(src_paths, workspace):
    for label, src_path in src_paths:
        shutil.copytree(
            os.path.expanduser(src_path),
            workspace / SOURCE_ROOT / label,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.svn')
        )


class MyCustomCodeFixes(Step):
    """
    An example of a custom step to fix some broken source code.

    """
    def run(self, artefacts, config):

        warnings.warn("SPECIAL MEASURE for io_configuration_mod.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            '~/git/fab/tmp-workspace/um_atmos_safe/source/um/io_services/common/io_configuration_mod.F90',
            '~/git/fab/tmp-workspace/um_atmos_safe/source/um/io_services/common/io_configuration_mod.F90',
            'NameListFile', 'FabNameListFile')

        warnings.warn("SPECIAL MEASURE for um_config.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            '~/git/fab/tmp-workspace/um_atmos_safe/source/um/control/top_level/um_config.F90',
            '~/git/fab/tmp-workspace/um_atmos_safe/source/um/control/top_level/um_config.F90',
            'NameListFile', 'FabNameListFile')

    def replace_in_file(self, inpath, outpath, find, replace):
        orig = open(os.path.expanduser(inpath), "rt").read()
        open(os.path.expanduser(outpath), "wt").write(
            case_insensitive_replace(in_str=orig, find=find, replace_with=replace))


if __name__ == '__main__':
    main()

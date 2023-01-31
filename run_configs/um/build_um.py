#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

# Note: we need this to run the exe
#   export LD_LIBRARY_PATH=~/.conda/envs/sci-fab/lib:$LD_LIBRARY_PATH

import logging
import os
import re
import warnings
from argparse import ArgumentParser

from fab.artefacts import CollectionGetter
from fab.build_config import AddFlags, BuildConfig
from fab.constants import PRAGMAD_C
from fab.steps import Step
from fab.steps.analyse import Analyse
from fab.steps.archive_objects import ArchiveObjects
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.grab.fcm.export import FcmExport
from fab.steps.link import LinkExe
from fab.steps.preprocess import c_preprocessor, fortran_preprocessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.find_source_files import FindSourceFiles, Exclude, Include

logger = logging.getLogger('fab')


# todo: fail fast, check gcom exists


def um_atmos_safe_config(revision, two_stage=False):
    um_revision = revision.replace('vn', 'um')

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler()
    if compiler == 'gfortran':
        compiler_specific_flags = ['-fdefault-integer-8', '-fdefault-real-8', '-fdefault-double-8']
    elif compiler == 'ifort':
        # compiler_specific_flags = ['-r8']
        compiler_specific_flags = [
            '-i8', '-r8', '-mcmodel=medium',
            '-no-vec', '-fp-model precise',
            '-std08',
            '-fpscomp logicals',
            '-g',
            '-diag-disable 6477',
            '-fpic',
            '-assume nosource_include,protect_parens',
        ]
    else:
        compiler_specific_flags = []

    config = BuildConfig(
        project_label=f'um atmos safe {revision} {compiler} {int(two_stage)+1}stage',
        # multiprocessing=False,
        # reuse_artefacts=True,
    )

    # Locate the gcom library. UM 12.1 intended to be used with gcom 7.6
    gcom_build = os.getenv('GCOM_BUILD') or os.path.normpath(os.path.expanduser(
        config.project_workspace / f"../gcom_object_archive_vn7.6_{compiler}/build_output"))
    if not os.path.exists(gcom_build):
        raise RuntimeError(f'gcom not found at {gcom_build}')

    config.steps = [

        # todo: these repo defs could make a good set of reusable variables

        # UM 12.1, 16th November 2021
        FcmExport(src='fcm:um.xm_tr/src', dst='um', revision=revision),

        # JULES 6.2, for UM 12.1
        FcmExport(src='fcm:jules.xm_tr/src', dst='jules', revision=um_revision),

        # SOCRATES 21.11, for UM 12.1
        FcmExport(src='fcm:socrates.xm_tr/src', dst='socrates', revision=um_revision),

        # SHUMLIB, for UM 12.1
        FcmExport(src='fcm:shumlib.xm_tr/', dst='shumlib', revision=um_revision),

        # CASIM, for UM 12.1
        FcmExport(src='fcm:casim.xm_tr/src', dst='casim', revision=um_revision),


        MyCustomCodeFixes(name="my custom code fixes"),

        FindSourceFiles(path_filters=file_filtering),

        RootIncFiles(),

        CPragmaInjector(),

        c_preprocessor(
            source=CollectionGetter(PRAGMAD_C),
            path_flags=[
                # todo: this is a bit "codey" - can we safely give longer strings and split later?
                AddFlags(match="$source/um/*", flags=[
                    '-I$source/um/include/other',
                    '-I$source/shumlib/common/src',
                    '-I$source/shumlib/shum_thread_utils/src']),

                AddFlags(match="$source/shumlib/*", flags=[
                    '-I$source/shumlib/common/src',
                    '-I$source/shumlib/shum_thread_utils/src']),

                # todo: just 3 folders use this
                AddFlags("$source/um/*", ['-DC95_2A', '-I$source/shumlib/shum_byteswap/src']),
            ],
        ),

        # todo: explain fnmatch
        fortran_preprocessor(
            common_flags=['-P'],
            path_flags=[
                AddFlags("$source/jules/*", ['-DUM_JULES']),
                AddFlags("$source/um/*", ['-I$relative/include']),

                # coupling defines
                AddFlags("$source/um/control/timer/*", ['-DC97_3A']),
                AddFlags("$source/um/io_services/client/stash/*", ['-DC96_1C']),
            ],
        ),

        Analyse(root_symbol='um_main'),

        CompileC(compiler='gcc', common_flags=['-c', '-std=c99']),

        CompileFortran(
            common_flags=[
                *compiler_specific_flags,
            ],
            two_stage_flag='-fsyntax-only' if two_stage else None,
            path_flags=[
                # mpl include - todo: just add this for everything?
                AddFlags("$output/um/*", ['-I' + gcom_build]),
                AddFlags("$output/jules/*", ['-I' + gcom_build]),

                # required for newer compilers
                # # todo: allow multiple filters per instance?
                # *[AddFlags(*i) for i in ALLOW_MISMATCH_FLAGS]
            ]
        ),

        # this step just makes linker error messages more manageable
        ArchiveObjects(),

        LinkExe(
            linker='mpifort',
            flags=[
                '-lc', '-lgfortran', '-L', '~/.conda/envs/sci-fab/lib',
                '-L', gcom_build, '-l', 'gcom'
            ],
        )
    ]
    return config


file_filtering = [
    Exclude('unit-test', 'unit_test', '/test/'),

    Exclude('/um/utility/'),
    Include('/um/utility/qxreconf/'),

    Exclude('/um/atmosphere/convection/comorph/interface/'),
    Include('/um/atmosphere/convection/comorph/interface/um/'),

    Exclude('/um/atmosphere/convection/comorph/unit_tests/'),

    Exclude('/um/scm/'),
    Include('/um/scm/stub/',
            '/um/scm/modules/s_scmop_mod.F90',
            '/um/scm/modules/scmoptype_defn.F90'),

    Exclude('/jules/'),
    Include('/jules/control/shared/',
            '/jules/control/um/',
            '/jules/control/rivers-standalone/',
            '/jules/initialisation/shared/',
            '/jules/initialisation/um/',
            '/jules/initialisation/rivers-standalone/',
            '/jules/params/um/',
            '/jules/science/',
            '/jules/util/shared/'),

    Exclude('/socrates/'),
    Include('/socrates/nlte/',
            '/socrates/radiance_core/'),

    # the shummlib config in fcm config doesn't seem to do anything,
    # perhaps there used to be extra files we needed to exclude
    Exclude('/shumlib/'),
    Include('/shumlib/shum_wgdos_packing/src',
            '/shumlib/shum_string_conv/src',
            '/shumlib/shum_latlon_eq_grids/src',
            '/shumlib/shum_horizontal_field_interp/src',
            '/shumlib/shum_spiral_search/src',
            '/shumlib/shum_constants/src',
            '/shumlib/shum_thread_utils/src',
            '/shumlib/shum_data_conv/src',
            '/shumlib/shum_number_tools/src',
            '/shumlib/shum_byteswap/src',
            '/shumlib/common/src'),
    Exclude('/shumlib/common/src/shumlib_version.c'),

    Exclude('/casim/mphys_die.F90',
            '/casim/mphys_casim.F90'),

    Exclude('.xml'),
    Exclude('.sh'),
]


# required for newer compilers

# # todo: allow a list of filters?
# ALLOW_MISMATCH_FLAGS = [
#     ('*/acumps.f90', ['-fallow-argument-mismatch']),
#     ('*/diagopr.f90', ['-fallow-argument-mismatch']),
#     ('*/eg_bi_linear_h.f90', ['-fallow-argument-mismatch']),
#     ('*/eg_sl_helmholtz_inc.f90', ['-fallow-argument-mismatch']),
#     ('*/emiss_io_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/fastjx_specs.f90', ['-fallow-argument-mismatch']),
#     ('*/glomap_clim_netcdf_io_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/halo_exchange_ddt_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/halo_exchange_mpi_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/halo_exchange_os_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/hardware_topology_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/history_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/imbnd_hill_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/io.f90', ['-fallow-argument-mismatch']),
#     ('*/io_configuration_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/io_server_listener.f90', ['-fallow-argument-mismatch']),
#     ('*/io_server_writer.f90', ['-fallow-argument-mismatch']),
#     ('*/ios.f90', ['-fallow-argument-mismatch']),
#     ('*/ios_client_queue.f90', ['-fallow-argument-mismatch']),
#     ('*/ios_comms.f90', ['-fallow-argument-mismatch']),
#     ('*/ios_init.f90', ['-fallow-argument-mismatch']),
#     ('*/ios_stash_server.f90', ['-fallow-argument-mismatch']),
#     ('*/lustre_control_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/mcica_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/mg_field_norm.f90', ['-fallow-argument-mismatch']),
#     ('*/nlstcall_nc_namelist_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/nlstcall_pp_namelist_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/num_obs.f90', ['-fallow-argument-mismatch']),
#     ('*/ppxlook_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/rdbasis.f90', ['-fallow-argument-mismatch']),
#     ('*/read_land_sea.f90', ['-fallow-argument-mismatch']),
#     ('*/regrid_alloc_calc_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/routedbl_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/setup_spectra_mod.f90', ['-fallow-argument-mismatch']),
#     ('*/ukca_scenario_rcp_mod.f90', ['-fallow-argument-mismatch']),
# ]


class MyCustomCodeFixes(Step):
    """
    An example of a custom step to fix some source code which fparser2 can't parse.

    """

    def run(self, artefact_store, config):
        warnings.warn("SPECIAL MEASURE for io_configuration_mod.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            config.project_workspace / 'source/um/io_services/common/io_configuration_mod.F90',
            config.project_workspace / 'source/um/io_services/common/io_configuration_mod.F90',
            r'(\W)NameListFile', r'\g<1>FabNameListFile')

        warnings.warn("SPECIAL MEASURE for um_config.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            config.project_workspace / 'source/um/control/top_level/um_config.F90',
            config.project_workspace / 'source/um/control/top_level/um_config.F90',
            r'(\W)NameListFile', r'\g<1>FabNameListFile')

    def replace_in_file(self, inpath, outpath, find, replace):
        orig = open(os.path.expanduser(inpath), "rt").read()
        open(os.path.expanduser(outpath), "wt").write(
            case_insensitive_replace(in_str=orig, find=find, replace_with=replace))


def case_insensitive_replace(in_str: str, find: str, replace_with: str):
    """
    Replace, for example, NameListFile *or* NAMELISTFILE with the given string.

    """
    compiled_re = re.compile(find, re.IGNORECASE)
    return compiled_re.sub(replace_with, in_str)


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--revision', default=os.getenv('UM_REVISION', 'vn12.1'))
    arg_parser.add_argument('--two-stage', action='store_true')
    args = arg_parser.parse_args()

    # logging.getLogger('fab').setLevel(logging.DEBUG)
    um_atmos_safe_config(revision=args.revision, two_stage=args.two_stage).run()

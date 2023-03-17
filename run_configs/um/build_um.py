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

from fab.artefacts import CollectionGetter
from fab.build_config import AddFlags, BuildConfig
from fab.constants import PRAGMAD_C
from fab.steps import step_timer
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.c_pragma_injector import c_pragma_injector
from fab.steps.compile_c import compile_c
from fab.steps.compile_fortran import compile_fortran, get_fortran_compiler
from fab.steps.grab.fcm import fcm_export
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_c, preprocess_fortran
from fab.steps.find_source_files import find_source_files, Exclude, Include
from run_configs.jules.build_jules import root_inc_files

logger = logging.getLogger('fab')


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


@step_timer
def my_custom_code_fixes(config):
    """
    An example of a custom step to fix some source code which fparser2 can't parse.

    """
    def replace_in_file(inpath, outpath, find, replace):
        orig = open(os.path.expanduser(inpath), "rt").read()
        open(os.path.expanduser(outpath), "wt").write(
            case_insensitive_replace(in_str=orig, find=find, replace_with=replace))

    warnings.warn("SPECIAL MEASURE for io_configuration_mod.F90: fparser2 misunderstands 'NameListFile'")
    replace_in_file(
        config.project_workspace / 'source/um/io_services/common/io_configuration_mod.F90',
        config.project_workspace / 'source/um/io_services/common/io_configuration_mod.F90',
        r'(\W)NameListFile', r'\g<1>FabNameListFile')

    warnings.warn("SPECIAL MEASURE for um_config.F90: fparser2 misunderstands 'NameListFile'")
    replace_in_file(
        config.project_workspace / 'source/um/control/top_level/um_config.F90',
        config.project_workspace / 'source/um/control/top_level/um_config.F90',
        r'(\W)NameListFile', r'\g<1>FabNameListFile')


def case_insensitive_replace(in_str: str, find: str, replace_with: str):
    """
    Replace, for example, NameListFile *or* NAMELISTFILE with the given string.

    """
    compiled_re = re.compile(find, re.IGNORECASE)
    return compiled_re.sub(replace_with, in_str)


if __name__ == '__main__':

    revision = 'vn12.1'
    um_revision = revision.replace('vn', 'um')

    # compiler-specific flags
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

    # todo: document: if you're changing compilers, put $compiler in your label
    with BuildConfig(project_label=f'um atmos safe {revision} $compiler $two_stage') as config:

        # todo: these repo defs could make a good set of reusable variables

        # UM 12.1, 16th November 2021
        fcm_export(config, src='fcm:um.xm_tr/src', dst_label='um', revision=revision)

        # JULES 6.2, for UM 12.1
        fcm_export(config, src='fcm:jules.xm_tr/src', dst_label='jules', revision=um_revision)

        # SOCRATES 21.11, for UM 12.1
        fcm_export(config, src='fcm:socrates.xm_tr/src', dst_label='socrates', revision=um_revision)

        # SHUMLIB, for UM 12.1
        fcm_export(config, src='fcm:shumlib.xm_tr/', dst_label='shumlib', revision=um_revision)

        # CASIM, for UM 12.1
        fcm_export(config, src='fcm:casim.xm_tr/src', dst_label='casim', revision=um_revision)

        my_custom_code_fixes(config)

        find_source_files(config, path_filters=file_filtering)

        root_inc_files(config)

        c_pragma_injector(config)

        preprocess_c(
            config,
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
        )

        # todo: explain fnmatch
        preprocess_fortran(
            config,
            common_flags=['-P'],
            path_flags=[
                AddFlags("$source/jules/*", ['-DUM_JULES']),
                AddFlags("$source/um/*", ['-I$relative/include']),

                # coupling defines
                AddFlags("$source/um/control/timer/*", ['-DC97_3A']),
                AddFlags("$source/um/io_services/client/stash/*", ['-DC96_1C']),
            ],
        )

        analyse(
            config, root_symbol='um_main',

            # # fparser2 fails to parse this file, but it does compile.
            # special_measure_analysis_results=[
            #     FortranParserWorkaround(
            #         fpath=Path(config.build_output / "casim/lookup.f90"),
            #         symbol_defs={'lookup'},
            #         symbol_deps={'mphys_die', 'variable_precision', 'mphys_switches', 'mphys_parameters', 'special',
            #                      'passive_fields', 'casim_moments_mod', 'yomhook', 'parkind1'},
            #     )
            # ]
        )

        compile_c(config, common_flags=['-c', '-std=c99'])

        # Locate the gcom library. UM 12.1 intended to be used with gcom 7.6
        gcom_build = os.getenv('GCOM_BUILD') or os.path.normpath(os.path.expanduser(
            config.project_workspace / f"../gcom_object_archive_{compiler}/build_output"))
        if not os.path.exists(gcom_build):
            raise RuntimeError(f'gcom not found at {gcom_build}')

        compile_fortran(
            config,
            common_flags=[
                *compiler_specific_flags,
            ],
            path_flags=[
                # mpl include - todo: just add this for everything?
                AddFlags("$output/um/*", ['-I' + gcom_build]),
                AddFlags("$output/jules/*", ['-I' + gcom_build]),

                # required for newer compilers
                # # todo: allow multiple filters per instance?
                # *[AddFlags(*i) for i in ALLOW_MISMATCH_FLAGS]
            ]
        )

        # this step just makes linker error messages more manageable
        archive_objects(config),

        link_exe(
            config,
            linker='mpifort',
            flags=[
                '-lc', '-lgfortran', '-L', '~/.conda/envs/sci-fab/lib',
                '-L', gcom_build, '-l', 'gcom'
            ],
        )

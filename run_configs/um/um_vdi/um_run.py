#!/usr/bin/env python
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

# Note: we need this to run the exe
#   export LD_LIBRARY_PATH=~/.conda/envs/sci-fab/lib:$LD_LIBRARY_PATH

import os
import warnings
from pathlib import Path

from fab.builder import Build
from fab.config import AddFlags, Config
from fab.dep_tree import AnalysedFile
from fab.steps import Step
from fab.steps.analyse import Analyse
from fab.steps.c_pragma_injector import CPragmaInjector
from fab.steps.compile_c import CompileC
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFcm
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import FortranPreProcessor, CPreProcessor
from fab.steps.root_inc_files import RootIncFiles
from fab.steps.walk_source import FindSourceFiles
from fab.util import TimerLogger, case_insensitive_replace
from fab.artefacts import CollectionGetter


def um_atmos_safe_config():
    project_name = 'um_atmos_safe'
    workspace = Path(os.path.dirname(__file__)) / "tmp-workspace" / project_name

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

        # build steps
        steps=[

            # todo: these repo defs could make a good set of reusable variables
            # UM 12.1, 16th November 2021
            GrabFcm(src='fcm:um.xm_tr/src', dst_label='um', revision=104450, name='grab um 12.1'),

            # JULES 6.2, for UM 12.1
            GrabFcm(src='fcm:jules.xm_tr/src', dst_label='jules', revision=21512, name='grab jules 6.2'),

            # SOCRATES 21.11, for UM 12.1
            GrabFcm(src='fcm:socrates.xm_tr/src', dst_label='socrates', revision=1126, name='grab socrates 21.11'),

            # SHUMLIB, for UM 12.1
            GrabFcm(src='fcm:shumlib.xm_tr/', dst_label='shumlib', revision=5658, name='grab shumblib for um 12.1'),

            # CASIM, for UM 12.1
            GrabFcm(src='fcm:casim.xm_tr/src', dst_label='casim', revision=9277, name='grab casim for um 12.1'),

            MyCustomCodeFixes(name="my custom code fixes"),

            FindSourceFiles(file_filtering=file_filtering),

            RootIncFiles(),

            CPragmaInjector(),

            CPreProcessor(
                source=CollectionGetter('pragmad_c'),
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
                            str(workspace / "build_output/casim/lookup.f90")),
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
                    '-c', '-fallow-argument-mismatch',
                    '-J', '$output',  # .mod file output and include folder
                ],

                path_flags=[
                    # mpl include - todo: just add this for everything?
                    AddFlags("$output/um/*", ['-I', str(workspace / '../gcom/build_output')]),
                    AddFlags("$output/jules/*",
                             ['-I', str(workspace / '../gcom/build_output')]),
                ]
            ),

            # todo: ArchiveObjects(),

            LinkExe(
                # linker='gcc',
                linker=os.path.expanduser('~/.conda/envs/sci-fab/bin/mpifort'),
                flags=[
                    '-lc', '-lgfortran', '-L', '~/.conda/envs/sci-fab/lib',
                    '-L', str(workspace / '../gcom/build_output'), '-l', 'gcom',
                ],
                output_fpath='$output/../um_atmos.exe')
        ],

    )


def main():

    # config
    config = um_atmos_safe_config()

    builder = Build(config=config)

    with TimerLogger("um build"):
        builder.run()


class MyCustomCodeFixes(Step):
    """
    An example of a custom step to fix some source code which fparser2 can't parse.

    """

    def run(self, artefact_store, config):
        warnings.warn("SPECIAL MEASURE for io_configuration_mod.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            config.workspace / 'source/um/io_services/common/io_configuration_mod.F90',
            config.workspace / 'source/um/io_services/common/io_configuration_mod.F90',
            r'(\W)NameListFile', r'\g<1>FabNameListFile')

        warnings.warn("SPECIAL MEASURE for um_config.F90: fparser2 misunderstands 'NameListFile'")
        self.replace_in_file(
            config.workspace / 'source/um/control/top_level/um_config.F90',
            config.workspace / 'source/um/control/top_level/um_config.F90',
            r'(\W)NameListFile', r'\g<1>FabNameListFile')

    def replace_in_file(self, inpath, outpath, find, replace):
        orig = open(os.path.expanduser(inpath), "rt").read()
        open(os.path.expanduser(outpath), "wt").write(
            case_insensitive_replace(in_str=orig, find=find, replace_with=replace))


if __name__ == '__main__':
    main()

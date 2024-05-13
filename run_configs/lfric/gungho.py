#!/usr/bin/env python3
# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import logging

from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files, Exclude
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.steps.psyclone import psyclone, preprocess_x90

from grab_lfric import lfric_source_config, gpl_utils_source_config
from lfric_common import configurator, fparser_workaround_stop_concatenation

logger = logging.getLogger('fab')


def get_transformation_script(fpath, config):
    ''':returns: the transformation script to be used by PSyclone.
    :rtype: Path

    '''
    optimisation_path = config.source_root / 'lfric' / 'miniapps' / 'gungho_model' / 'optimisation' / 'meto-spice'
    local_transformation_script = optimisation_path / (fpath.relative_to(config.source_root).with_suffix('.py'))
    if local_transformation_script.exists():
        return local_transformation_script
    global_transformation_script = optimisation_path / 'global.py'
    if global_transformation_script.exists():
        return global_transformation_script
    return ""


if __name__ == '__main__':
    lfric_source = lfric_source_config.source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config.source_root / 'gpl_utils'

    with BuildConfig(project_label='gungho $compiler $two_stage') as state:
        grab_folder(state, src=lfric_source / 'infrastructure/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'components/driver/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'components' / 'inventory' / 'source', dst_label='')
        grab_folder(state, src=lfric_source / 'components/science/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'components/lfric-xios/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'gungho/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'um_physics/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'miniapps' / 'gungho_model' / 'source', dst_label='')

        grab_folder(state, src=lfric_source / 'jules/source/', dst_label='')
        grab_folder(state, src=lfric_source / 'socrates/source/', dst_label='')

        # generate more source files in source and source/configuration
        configurator(
            state,
            lfric_source=lfric_source,
            gpl_utils_source=gpl_utils_source,
            rose_meta_conf=lfric_source / 'miniapps' / 'gungho_model'
                                        / 'rose-meta' / 'lfric-gungho_model'
                                        / 'HEAD' / 'rose-meta.conf',
        )

        find_source_files(state, path_filters=[Exclude('unit-test', '/test/')])

        preprocess_fortran(
            state,
            common_flags=[
                '-DRDEF_PRECISION=64', '-DR_SOLVER_PRECISION=64', '-DR_TRAN_PRECISION=64', '-DUSE_XIOS',
            ])

        preprocess_x90(state, common_flags=['-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DCOUPLED'])

        psyclone(
            state,
            kernel_roots=[state.build_output],
            transformation_script=get_transformation_script,
            cli_args=[],
        )

        fparser_workaround_stop_concatenation(state)

        analyse(
            state,
            root_symbol='gungho_model',
            ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        )

        compile_fortran(
            state,
            common_flags=[
                '-c',
                '-ffree-line-length-none', '-fopenmp',
                '-g',
                '-std=f2008',

                '-Wall', '-Werror=conversion', '-Werror=unused-variable', '-Werror=character-truncation',
                '-Werror=unused-value', '-Werror=tabs',

                '-DRDEF_PRECISION=64', '-DR_SOLVER_PRECISION=64', '-DR_TRAN_PRECISION=64',
                '-DUSE_XIOS', '-DUSE_MPI=YES',
            ],
        )

        archive_objects(state)

        link_exe(
            state,
            linker='mpifort',
            flags=[
                '-fopenmp',

                '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',  # EXTERNAL_DYNAMIC_LIBRARIES
                '-lxios',  # EXTERNAL_STATIC_LIBRARIES
                '-lstdc++',
            ],
        )

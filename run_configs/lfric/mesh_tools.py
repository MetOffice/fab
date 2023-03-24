#!/usr/bin/env python3
from pathlib import Path


from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.archive_objects import archive_objects
from fab.steps.compile_fortran import compile_fortran
from fab.steps.grab.folder import grab_folder
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.steps.find_source_files import find_source_files, Exclude
from fab.steps.psyclone import psyclone, preprocess_x90

from lfric_common import configurator, fparser_workaround_stop_concatenation
from grab_lfric import lfric_source_config, gpl_utils_source_config


if __name__ == '__main__':
    lfric_source = lfric_source_config.source_root / 'lfric'
    gpl_utils_source = gpl_utils_source_config.source_root / 'gpl_utils'

    # this folder just contains previous output, for testing the overrides mechanism.
    psyclone_overrides = Path(__file__).parent / 'mesh_tools_overrides'

    with BuildConfig(project_label='mesh tools $compiler $two_stage') as config:
        grab_folder(config, src=lfric_source / 'infrastructure/source/', dst_label='')
        grab_folder(config, src=lfric_source / 'mesh_tools/source/', dst_label='')
        grab_folder(config, src=lfric_source / 'components/science/source/', dst_label='')

        grab_folder(config, src=lfric_source / 'gungho/source/', dst_label='')

        # grab the psyclone overrides folder into the source folder
        grab_folder(config, src=psyclone_overrides, dst_label='mesh_tools_overrides')

        # generate more source files in source and source/configuration
        configurator(
            config,
            lfric_source=lfric_source,
            gpl_utils_source=gpl_utils_source,
            rose_meta_conf=lfric_source / 'mesh_tools/rose-meta/lfric-mesh_tools/HEAD/rose-meta.conf',
        )

        find_source_files(
            config,
            path_filters=[
                # todo: allow a single string
                Exclude('unit-test', '/test/'),
            ])

        preprocess_fortran(config)

        preprocess_x90(config, common_flags=['-DRDEF_PRECISION=64', '-DUSE_XIOS', '-DCOUPLED'])

        psyclone(
            config,
            kernel_roots=[config.build_output],
            cli_args=['--config', Path(__file__).parent / 'psyclone.cfg'],
            overrides_folder=config.source_root / 'mesh_tools_overrides',
        )

        fparser_workaround_stop_concatenation(config)

        analyse(
            config,
            root_symbol=['cubedsphere_mesh_generator', 'planar_mesh_generator', 'summarise_ugrid'],
            # ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        )

        compile_fortran(config, common_flags=['-c'])

        archive_objects(config)

        # link the 3 trees' objects
        link_exe(
            config,
            linker='mpifort',
            flags=[
                '-lyaxt', '-lyaxt_c', '-lnetcdff', '-lnetcdf', '-lhdf5',  # EXTERNAL_DYNAMIC_LIBRARIES
                '-lxios',  # EXTERNAL_STATIC_LIBRARIES
                '-lstdc++',
            ],
        )

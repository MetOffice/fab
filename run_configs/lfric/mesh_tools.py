from fab.steps.analyse import Analyse

from fab.constants import BUILD_OUTPUT

from fab.steps.preprocess import fortran_preprocessor

from fab.steps.walk_source import FindSourceFiles

from fab.steps.grab import GrabFolder

from fab.build_config import BuildConfig
from run_configs.lfric.grab_lfric import lfric_source, gpl_utils_source
from run_configs.lfric.lfric_common import Configurator, psyclone_preprocessor, Psyclone, \
    FparserWorkaround_StopConcatenation


def mesh_tools():
    lfric_source_config = lfric_source()

    config = BuildConfig(project_label='mesh_tools')
    config.steps = [

        GrabFolder(src=lfric_source_config.source_root / 'lfric/infrastructure/source/', dst_label=''),
        GrabFolder(src=lfric_source_config.source_root / 'lfric/mesh_tools/source/', dst_label=''),

        # generate more source files in source and source/configuration
        Configurator(
            lfric_source=lfric_source_config.source_root / 'lfric',
            gpl_utils_source=gpl_utils_source().source_root / 'gpl_utils'),

        FindSourceFiles(file_filtering=[
            # todo: allow a single string
            (['unit-test', '/test/'], False),
        ]),

        fortran_preprocessor(preprocessor='cpp -traditional-cpp', common_flags=['-P']),

        psyclone_preprocessor(),

        Psyclone(kernel_roots=[config.project_workspace / BUILD_OUTPUT]),

        FparserWorkaround_StopConcatenation(name='fparser stop bug workaround'),

        Analyse(
            root_symbol=['cubedsphere_mesh_generator', 'planar_mesh_generator', 'summarise_ugrid'],
            # ignore_mod_deps=['netcdf', 'MPI', 'yaxt', 'pfunit_mod', 'xios', 'mod_wait'],
        ),

        # todo:
        # compile one big lump
        # link the 3 trees' objects

    ]

    return config


if __name__ == '__main__':
    mesh_tools().run()

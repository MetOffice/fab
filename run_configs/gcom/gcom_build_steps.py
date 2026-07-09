##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.api import (analyse, compile_c, compile_fortran, find_source_files,
                     grab_folder, preprocess_c, preprocess_fortran)

from grab_gcom import grab_config


def common_build_steps(config, fpic=False):

    fpp_flags = [
        '-P',
        '-I$source/gcom/include',
        '-DGC_VERSION="7.6"',
        '-DGC_BUILD_DATE="20220111"',
        '-DGC_DESCRIP="dummy desrip"',
        '-DPREC_64B', '-DMPILIB_32B',
    ]

    fpic = ['-fPIC'] if fpic else []

    grab_folder(config, src=grab_config.source_root),
    find_source_files(config),
    preprocess_c(config),  # todo: there's no c! :)
    preprocess_fortran(config, common_flags=fpp_flags),
    analyse(config),
    compile_c(config, common_flags=['-c', '-std=c99'] + fpic),
    compile_fortran(config, common_flags=fpic),

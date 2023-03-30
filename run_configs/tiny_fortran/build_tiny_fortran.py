#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.git import git_checkout
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran


if __name__ == '__main__':

    with BuildConfig(project_label='tiny_fortran $compiler') as state:
        git_checkout(state, src='https://github.com/metomi/fab-test-data.git', revision='main', dst_label='src'),

        find_source_files(state),

        preprocess_fortran(state),

        analyse(state, root_symbol='my_prog'),

        compile_fortran(state),
        link_exe(state, linker='mpifort'),

#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran, get_fortran_compiler
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab import GrabGit
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.util import common_arg_parser

logger = logging.getLogger('fab')


def config(compiler=None):

    # We want a separate project folder for each compiler. Find out which compiler we'll be using.
    compiler, _ = get_fortran_compiler(compiler)
    config = BuildConfig(project_label=f'tiny_fortran {compiler}')

    logger.info(f'building tiny fortran {config.project_label}')

    config.steps = [

        GrabGit(src='https://github.com/bblay/tiny_fortran.git', revision='main', dst='src'),

        FindSourceFiles(),

        fortran_preprocessor(preprocessor='fpp -P'),

        Analyse(root_symbol='my_prog'),

        CompileFortran(compiler=compiler),
        LinkExe(linker='mpifort'),
    ]

    return config


if __name__ == '__main__':
    arg_parser = common_arg_parser()
    args = arg_parser.parse_args()

    config(compiler=args.compiler).run()

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Command-line interface to Fab build tool.
'''
import argparse
import logging
from pathlib import Path
import sys

import fab.application


def parse_cli() -> argparse.Namespace:
    '''
    Parse the command line for arguments.
    '''
    description = 'Flexible build system for scientific software.'
    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    parser.add_argument('-h', '-help', '--help', action='help',
                        help='Print this help and exit')
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help='Print version identifier and exit')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Produce a running commentary on progress')
    parser.add_argument('-w', '--workspace', metavar='FILENAME', type=Path,
                        help='Directory for working files')
    parser.add_argument('--fpp-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran PreProcessor ')
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build')
    return parser.parse_args()


def main() -> None:
    '''
    Entry point for command-line tool.
    '''
    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stdout))

    arguments = parse_cli()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if not arguments.workspace:
        arguments.workspace = arguments.source / 'working'

    application = fab.application.Fab(arguments.workspace,
                                      arguments.fpp_flags)
    application.run(arguments.source)


if __name__ == '__main__':
    main()

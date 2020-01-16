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
import sys
import os

import fab
from fab.language.fortran import reader

_extensions = [
    'F90',
    'f90',
    ]


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
    parser.add_argument('source',
                        help='The path to the source tree to build')
    return parser.parse_args()


def sourcepath_iter(rootpath: str) -> str:
    '''
    Return files we can process from the source tree.
    '''
    for root, _, files in os.walk(rootpath):
        for name in files:
            if name.split(".")[-1] in _extensions:
                yield os.path.join(root, name)


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

    for sourcefile in sourcepath_iter(arguments.source):
        print(f'Processing {sourcefile}:')
        print(''.join(reader.sourcefile_iter(sourcefile)))
        print(f'Processed {sourcefile}\n')

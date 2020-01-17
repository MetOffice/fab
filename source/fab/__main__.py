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
from pathlib import Path
from typing import Generator

import fab
from fab.language.fortran import reader

_extensions = [
    '.F90',
    '.f90',
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


def rootpath_iter(rootpath: Path) -> Generator[Path, None, None]:
    '''
    Return files we can process from the source tree.
    '''
    for path in rootpath.rglob("*"):
        if path.suffix in _extensions:
            yield path


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

    rootpath = Path(arguments.source)

    for sourcepath in rootpath_iter(rootpath):
        msg = '{0:s}\n! {1:s}\n{0:s}'
        print(msg.format("!" + "#" * (len(sourcepath.name)+1),
                         sourcepath.name))
        print('\n'.join(reader.sourcefile_iter(sourcepath)))

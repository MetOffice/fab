'''
Command-line interface to Fab build tool.
'''
import argparse
import logging
import sys

import fab


def parse_cli() -> argparse.Namespace:
    '''
    Parse the command line for arguments.
    '''
    description='Flexible build system for scientific software.'
    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    parser.add_argument('-help', '-h', '--help', action='help',
                        help='Print this help and exit')
    parser.add_argument('-version', action='version', version=fab.__version__)
    parser.add_argument('-verbose', action='store_true',
                        help='Produce a running commentary on progress')
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

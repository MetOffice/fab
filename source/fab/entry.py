##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Entry points for tools in the Fab suite of build related tools.
"""
import argparse
import logging
from pathlib import Path
import sys

import fab.application


def fab_cli() -> argparse.Namespace:
    """
    Parses command line arguments for the core Fab build tool.
    """
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
                        help='Directory for working files.')
    # TODO: Flags will eventually come from configuration
    parser.add_argument('--fpp-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran PreProcessor ')
    # TODO: Flags will eventually come from configuration
    parser.add_argument('--fc-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran Compiler')
    # TODO: Flags will eventually come from configuration
    parser.add_argument('--ld-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran Linker')
    # TODO: Name for executable will eventually come from configuration
    parser.add_argument('--exec-name', action='store', type=str, default='',
                        help='Name of executable (default is the name of '
                        'the program with extentsion ".exe")')
    # TODO: Target/s will eventually come from configuration
    parser.add_argument('target', action='store', type=str,
                        help='The top level unit name to compile')
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build')
    return parser.parse_args()


def fab_entry() -> None:
    """
    The core Fab build tool.
    """
    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stderr))

    arguments = fab_cli()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if not arguments.workspace:
        arguments.workspace = arguments.source / 'working'

    application = fab.application.Fab(arguments.workspace,
                                      arguments.target,
                                      arguments.exec_name,
                                      arguments.fpp_flags,
                                      arguments.fc_flags,
                                      arguments.ld_flags)
    application.run(arguments.source)


def dump_cli() -> argparse.Namespace:
    """
    Parse command line arguments for the dumper tool.
    """
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
                        help='Directory for working files.')
    return parser.parse_args()


def dump_entry() -> None:
    """
    Dump a state database from a working directory.
    """
    logger = logging.getLogger('fab-dumper')
    logger.addHandler(logging.StreamHandler(sys.stderr))

    arguments = dump_cli()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if not arguments.workspace:
        arguments.workspace = Path.cwd() / 'working'

    application = fab.application.Dump(arguments.workspace)
    application.run()


if __name__ == '__main__':
    raise Exception("Invoke using entry points only")

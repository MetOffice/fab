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
import multiprocessing
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
                        default=Path.cwd() / 'working',
                        help='Directory for working files.')
    parser.add_argument('--nprocs', action='store', type=int, default=2,
                        choices=range(2, multiprocessing.cpu_count()),
                        help='Provide number of processors available for use,'
                             'default is 2 if not set.')
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
                        'the target program)')
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

    application = fab.application.Fab(arguments.workspace,
                                      arguments.target,
                                      arguments.exec_name,
                                      arguments.fpp_flags,
                                      arguments.fc_flags,
                                      arguments.ld_flags,
                                      arguments.nprocs)
    application.run(arguments.source)


def grab_cli() -> argparse.Namespace:
    """
    Parse command line arguments for extraction tool.
    """
    description = "Build a source tree from extracted source."
    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    parser.add_argument('-h', '-help', '--help', action='help',
                        help="Print this help and exit.")
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help="Print version identifier and exit.")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Produce a running commentary on progress.")
    parser.add_argument('-w', '--workspace', metavar='FILENAME', type=Path,
                        default=Path.cwd() / 'working',
                        help="Directory for working files.")
    parser.add_argument('repositories', nargs='+', metavar='URL',
                        help="Location from which to extract source.")
    return parser.parse_args()


def grab_entry() -> None:
    """
    Extract and merge up a source tree from several repositories.
    """
    logger = logging.getLogger('fab-grab')
    logger.addHandler(logging.StreamHandler(sys.stderr))

    arguments = grab_cli()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

        application = fab.application.Grab(arguments.workspace)
        application.run(arguments.repositories)


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
                        default=Path.cwd() / 'working',
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

    application = fab.application.Dump(arguments.workspace)
    application.run()


def explorer_cli() -> argparse.Namespace:
    """
    Parse the command line for database explorer arguments.
    """
    description = "Explore a Fab state database."
    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    # We add our own help so as to capture as many permutations of how people
    # might ask for help. The default only looks for a subset.
    parser.add_argument('-h', '-help', '--help', action='help',
                        help="Print this help and exit")
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help="Print version identifier and exit")
    parser.add_argument('-w', '--workspace', type=Path,
                        default=Path.cwd() / 'working',
                        help="Directory containing working files.")
    return parser.parse_args()


def fab_explorer() -> None:
    """
    Entry point for database exploration tool.
    """
    arguments = explorer_cli()

    application = fab.application.Explorer(arguments.workspace)
    application.run()


if __name__ == '__main__':
    raise Exception("Invoke using entry points only")

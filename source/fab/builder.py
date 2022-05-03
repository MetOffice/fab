##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A build config contains a list of steps, each with a run method which it calls one at a time.
Each step can access the artifacts created by previous steps, and add their own.

"""
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path

from fab.config import Config
from fab.constants import BUILD_OUTPUT
from fab.util import time_logger

logger = logging.getLogger(__name__)

runtime_str = datetime.now().strftime("%Y%m%d_%H%M%S")


# todo: uncomment and get this working again
def entry() -> None:
    """
    Entry point for the Fab build tool.
    """
    import argparse
    import fab

    description = 'Flexible build system for scientific software.'

    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    # We add our own help so as to capture as many permutations of how people
    # might ask for help. The default only looks for a subset.
    parser.add_argument('-h', '-help', '--help', action='help',
                        help='Print this help and exit')
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help='Print version identifier and exit')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbosity (may be specified once '
                             'for moderate and twice for debug verbosity)')
    parser.add_argument('-w', '--workspace', metavar='PATH', type=Path,
                        default=Path.cwd() / 'working',
                        help='Directory for working files.')
    parser.add_argument('--nprocs', action='store', type=int, default=2,
                        choices=range(2, multiprocessing.cpu_count()),
                        help='Provide number of processors available for use,'
                             'default is 2 if not set.')
    parser.add_argument('--skip-if-exists', action="store_true")
    # todo: this won't work with multiple source folders
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build.')
    parser.add_argument('conf_file', type=Path, default='config.ini',
                        help='The path of the configuration file')
    arguments = parser.parse_args()

    verbosity_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    verbosity = min(arguments.verbose, 2)
    logger.setLevel(verbosity_levels[verbosity])


class Build(object):
    def __init__(self, config: Config):
        self.config = config

        if not config.workspace.exists():
            config.workspace.mkdir(parents=True)
        if not (config.workspace / BUILD_OUTPUT).exists():
            (config.workspace / BUILD_OUTPUT).mkdir()

    def run(self):
        logger.info(f"{datetime.now()}")
        logger.info(f"use_multiprocessing = {self.config.use_multiprocessing}")
        if self.config.use_multiprocessing:
            logger.info(f"n_procs = {self.config.n_procs}")

        artefact_store = dict()
        for step in self.config.steps:
            with time_logger(step.name):
                step.run(artefact_store, self.config)

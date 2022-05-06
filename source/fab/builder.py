##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A build config contains a list of steps, each with a run method which it calls one at a time.
Each step can access the artifacts created by previous steps, and add their own.

"""
import getpass
import logging
import multiprocessing
import os
from datetime import datetime
from pathlib import Path

from fab.metrics import init_metrics, stop_metrics, metrics_summary, send_metric

from fab.config import Config
from fab.constants import BUILD_OUTPUT
from fab.util import TimerLogger

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
        self.metrics_folder = None

        if not config.workspace.exists():
            config.workspace.mkdir(parents=True)
        if not (config.workspace / BUILD_OUTPUT).exists():
            (config.workspace / BUILD_OUTPUT).mkdir()

    def run(self):
        self.init_logging()
        self.init_metrics()

        artefact_store = dict()
        try:
            with TimerLogger(f'running {self.config.label} build steps') as steps_timer:
                for step in self.config.steps:
                    with TimerLogger(step.name) as step_timer:
                        step.run(artefact_store=artefact_store, config=self.config)
                    send_metric('steps', step.name, step_timer.taken)
        except Exception as err:
            raise Exception(f'\n\nError running build steps:\n{err}')
        finally:
            self.finalise_metrics(steps_timer.taken)

    def init_logging(self):
        logger.info(f"{datetime.now()}")
        if self.config.multiprocessing:
            logger.info(f'machine cores: {multiprocessing.cpu_count()}')
            logger.info(f'available cores: {len(os.sched_getaffinity(0))}')
            logger.info(f'using n_procs = {self.config.n_procs}')
        logger.info(f"workspace is {self.config.workspace}")

    def init_metrics(self):
        self.metrics_folder = self.config.workspace / 'metrics' / self.config.label.replace(' ', '_')

        init_metrics(metrics_folder=self.metrics_folder)

        send_metric(group='run', name='label', value=self.config.label)
        send_metric(group='run', name='datetime', value=datetime.now().replace(microsecond=0).isoformat())
        send_metric(group='run', name='sysname', value=os.uname().sysname)
        send_metric(group='run', name='nodename', value=os.uname().nodename)
        send_metric(group='run', name='machine', value=os.uname().machine)
        send_metric(group='run', name='user', value=getpass.getuser())

        if self.config.multiprocessing:
            send_metric(group='run', name='machine cores', value=multiprocessing.cpu_count())
            send_metric(group='run', name='available cores', value=len(os.sched_getaffinity(0)))
            send_metric(group='run', name='using n_procs', value=self.config.n_procs)

    def finalise_metrics(self, time_taken):
        send_metric(group='run', name='time taken', value=time_taken)

        stop_metrics()
        metrics_summary(metrics_folder=self.metrics_folder)

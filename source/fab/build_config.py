##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Contains the :class:`~fab.build_config.BuildConfig` and helper classes.

"""
import getpass
import logging
import os
from datetime import datetime
from fnmatch import fnmatch
from logging.handlers import RotatingFileHandler
from multiprocessing import cpu_count
from pathlib import Path
from string import Template
from typing import List, Optional

from fab.constants import BUILD_OUTPUT, SOURCE_ROOT
from fab.metrics import send_metric, init_metrics, stop_metrics, metrics_summary
from fab.steps import Step
from fab.util import TimerLogger, by_type

logger = logging.getLogger(__name__)


class BuildConfig(object):
    """
    Contains and runs a list of build steps.

    """

    def __init__(self, project_label: str, source_root: Optional[Path] = None, steps: Optional[List[Step]] = None,
                 multiprocessing=True, n_procs: int = None, reuse_artefacts=False,
                 fab_workspace: Optional[Path] = None):
        """
        :param str project_label:
            Name of the build project. The project workspace folder is created from this name, with spaces replaced
            by underscores.
        :param Path source_root:
            Optional argument to allow the config to find source code outside it's project workspace.
            This is useful, for example, when the :py:mod:`fab.steps.grab <grab>` is in a separate script to be run
            less frequently. In this scenario, the source code will be found in a different project workspace folder.
        :param List[Step] steps:
            The list of build steps to run.
        :param bool multiprocessing:
            An option to disable multiprocessing to aid debugging.
        :param int n_procs:
            The number of cores to use for multiprocessing operations. Defaults to the number of available cores.
        :param bool reuse_artefacts:
            A flag to avoid reprocessing certain files on subsequent runs.
            WARNING: Currently unsophisticated, this flag should only be used by Fab developers.
            The logic behind flag will soon be improved, in a work package called "incremental build".
        :param fab_workspace:
            Overrides the FAB_WORKSPACE environment variable.
            If not set, and FAB_WORKSPACE is not set, the fab workspace defaults to *~/fab-workspace*.

        """
        self.project_label: str = project_label

        # workspace folder
        if not fab_workspace:
            if os.getenv("FAB_WORKSPACE"):
                fab_workspace = Path(os.getenv("FAB_WORKSPACE"))  # type: ignore
            else:
                fab_workspace = Path(os.path.expanduser("~/fab-workspace"))
                logger.info(f"FAB_WORKSPACE not set. Defaulting to {fab_workspace}.")
        logger.info(f"fab workspace is {fab_workspace}.")

        self.project_workspace = fab_workspace / (project_label.replace(' ', '-'))
        self.metrics_folder = self.project_workspace / 'metrics' / self.project_label.replace(' ', '_', -1)

        # source config
        self.source_root: Path = source_root or self.project_workspace / SOURCE_ROOT

        # build steps
        self.steps: List[Step] = steps or []

        # multiprocessing config
        self.multiprocessing = multiprocessing
        self.n_procs = n_procs
        if self.multiprocessing and not self.n_procs:
            self.n_procs = max(1, len(os.sched_getaffinity(0)))

        self.reuse_artefacts = reuse_artefacts

    def run(self):
        """
        Execute the build steps in order.

        This function also records metrics and creates a summary, including charts if matplotlib is installed.
        The metrics can be found in the project workspace.

        """
        start_time = datetime.now().replace(microsecond=0)
        (self.project_workspace / BUILD_OUTPUT).mkdir(parents=True, exist_ok=True)

        self._init_logging()
        init_metrics(metrics_folder=self.metrics_folder)

        artefact_store = dict()
        try:
            with TimerLogger(f'running {self.project_label} build steps') as steps_timer:
                for step in self.steps:
                    with TimerLogger(step.name) as step_timer:
                        step.run(artefact_store=artefact_store, config=self)
                    send_metric('steps', step.name, step_timer.taken)
        except Exception as err:
            logger.error(f'\n\nError running build steps:\n{err}')
            raise Exception(f'\n\nError running build steps:\n{err}')
        finally:
            self._finalise_metrics(start_time, steps_timer)
            self._finalise_logging()

    def _init_logging(self):
        # add a file logger for our run
        log_file_handler = RotatingFileHandler(self.project_workspace / 'log.txt', backupCount=5, delay=True)
        log_file_handler.doRollover()
        logging.getLogger('fab').addHandler(log_file_handler)

        logger.info(f"{datetime.now()}")
        if self.multiprocessing:
            logger.info(f'machine cores: {cpu_count()}')
            logger.info(f'available cores: {len(os.sched_getaffinity(0))}')
            logger.info(f'using n_procs = {self.n_procs}')
        logger.info(f"workspace is {self.project_workspace}")

    def _finalise_logging(self):
        # remove our file logger
        fab_logger = logging.getLogger('fab')
        log_file_handlers = list(by_type(fab_logger.handlers, RotatingFileHandler))
        assert len(log_file_handlers) == 1
        fab_logger.removeHandler(log_file_handlers[0])

    def _finalise_metrics(self, start_time, steps_timer):
        send_metric('run', 'label', self.project_label)
        send_metric('run', 'datetime', start_time.isoformat())
        send_metric('run', 'time taken', steps_timer.taken)
        send_metric('run', 'sysname', os.uname().sysname)
        send_metric('run', 'nodename', os.uname().nodename)
        send_metric('run', 'machine', os.uname().machine)
        send_metric('run', 'user', getpass.getuser())
        stop_metrics()
        metrics_summary(metrics_folder=self.metrics_folder)


# todo: better name? perhaps PathFlags?
class AddFlags(object):
    """
    Add command-line flags when our path filter matches.
    Generally used inside a :class:`~fab.build_config.FlagsConfig`.

    """
    def __init__(self, match: str, flags: List[str]):
        """
        :param match:
            The string to match against each file path.
        :param flags:
            The command-line flags to add for matching files.

        Both the *match* and *flags* arguments can make use of templating.

        For example::

            # For source in the um folder, add an absolute include path
            AddFlags(match="$source/um/*", flags=['-I$source/include']),

            # For source in the um folder, add an include path relative to each source file.
            AddFlags(match="$source/um/*", flags=['-I$relative/include']),

        """
        self.match: str = match
        self.flags: List[str] = flags

    # todo: we don't need the project_workspace, we could just pass in the output folder
    def run(self, fpath: Path, input_flags: List[str], source_root: Path, project_workspace: Path):
        """
        Check if our filter matches a given file. If it does, add our flags.

        :param fpath:
            Filepath to check.
        :param input_flags:
            The list of command-line flags Fab is building for this file.
        :param source_root:
            For templating `$source`.
        :param project_workspace:
            For templating `$output`.

        """
        params = {'relative': fpath.parent, 'source': source_root, 'output': project_workspace / BUILD_OUTPUT}

        # does the file path match our filter?
        if not self.match or fnmatch(str(fpath), Template(self.match).substitute(params)):
            # use templating to render any relative paths in our flags
            add_flags = [Template(flag).substitute(params) for flag in self.flags]

            # add our flags
            input_flags += add_flags


class FlagsConfig(object):
    """
    Return command-line flags for a given path.

    Simply allows appending flags but may evolve to also replace and remove flags.

    """

    def __init__(self, common_flags: Optional[List[str]] = None, path_flags: Optional[List[AddFlags]] = None):
        """
        :param common_flags:
            Flags to apply to all files.
        :param path_flags:
            Flags to apply to selected files.

        """
        self.common_flags = common_flags or []
        self.path_flags = path_flags or []

    # todo: there's templating both in this method and the run method it calls.
    #       make sure it's all properly documented and rationalised.
    def flags_for_path(self, path: Path, source_root: Path, project_workspace: Path):
        """
        Get all the flags for a given file, in a reproducible order.

        :param path:
            The file path for which we want command-line flags.
        :param source_root:
            Passed through for templating.
        :param project_workspace:
            Passed through for templating.

        """
        # We COULD make the user pass these template params to the constructor
        # but we have a design requirement to minimise the config burden on the user,
        # so we take care of it for them here instead.
        params = {'source': source_root, 'output': project_workspace / BUILD_OUTPUT}
        flags = [Template(i).substitute(params) for i in self.common_flags]

        for flags_modifier in self.path_flags:
            flags_modifier.run(path, flags, source_root=source_root, project_workspace=project_workspace)

        return flags

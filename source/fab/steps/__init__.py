##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Predefined build steps with sensible defaults.

"""
import multiprocessing
from abc import ABC, abstractmethod
from typing import Dict

from fab.util import by_type


class Step(ABC):
    """
    Base class for build steps.

    Provides multiprocessing capabilities which can be disabled for debugging.

    """

    def __init__(self, name):
        """
        :param name:
            Human friendly name for logger output. Steps generally provide a sensible default.

        """
        self.name = name

        # runtime
        self._config = None

    @abstractmethod
    def run(self, artefact_store: Dict, config):
        """
        Process artefact collections from previous steps, creating a new artefact collection. Defined in the subclass.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        For the duration of this run, the given config will be available to all our methods as `self._config`.
        This is useful for multiprocessing steps, where it's cleanest to pass a list of artifacts through a function.
        In this case it's messy to also pass the config, so setting it here makes it available to all our methods.

        """
        self._config = config

    def run_mp(self, items, func, no_multiprocessing: bool = False):
        """
        Called from Step.run() to process multiple items in parallel.

        For example, a compile step would, in its run() method, find a list of source files in the artefact store.
        It could then pass those paths to this method, along with a function to compile a *single* file.
        The whole set of results are returned in a list-like, with undefined order.

        :param items:
            An iterable of items to process in parallel.
        :param func:
            A function to process a single item. Must accept a single argument.
        :param no_multiprocessing:
            Overrides the config's multiprocessing flag, disabling multiprocessing for this call.

        """
        if self._config.multiprocessing and not no_multiprocessing:
            with multiprocessing.Pool(self._config.n_procs) as p:
                results = p.map(func, items)
        else:
            results = [func(f) for f in items]

        return results

    def run_mp_imap(self, items, func, result_handler):
        """
        Like run_mp, but uses imap instead of map so that we can process each result as it happens.

        This is useful for a slow operation where we want to save our progress as we go
        instead of waiting for everything to finish, allowing us to pick up where we left off if the program is halted.

        :param items:
            An iterable of items to process in parallel.
        :param func:
            A function to process a single item. Must accept a single argument.
        :param result_handler:
            A function to handle a single result. Must accept a single argument.

        """
        if self._config.multiprocessing:
            with multiprocessing.Pool(self._config.n_procs) as p:
                analysis_results = p.imap_unordered(func, items)
                result_handler(analysis_results)
        else:
            analysis_results = (func(a) for a in items)  # generator
            result_handler(analysis_results)


def check_for_errors(results, caller_label=None):
    """
    Check an iterable of results for any exceptions and handle them gracefully.

    This is a helper function for steps which use multiprocessing,
    getting multiple results back from :meth:`~fab.steps.Step.run_mp` all in one go.

    :param results:
        An iterable of results.
    :param caller_label:
        Optional human-friendly name of the caller for logging.

    """
    caller_label = f'during {caller_label}' if caller_label else ''

    exceptions = list(by_type(results, Exception))
    if exceptions:
        formatted_errors = "\n\n".join(map(str, exceptions))
        raise RuntimeError(
            f"{formatted_errors}\n\n{len(exceptions)} error(s) found {caller_label}"
        )

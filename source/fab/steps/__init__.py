##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import multiprocessing
from typing import Dict


class Step(object):
    """
    Base class for build steps.

    Provides multiprocessing capabilities which can be disabled for debugging.

    """

    def __init__(self, name):
        self.name = name

    # @abstractmethod
    # todo: too much to send the whole config through?
    #       it allows step manipulation, adding steps, etc
    #       but it could let things get into a mess? discuss...
    def run(self, artefacts: Dict, config):
        """
        Process some input artefacts, create some output artefacts. Defined by the subclass.

        Args:
            - artefacts: Build artefacts created by previous Steps, to which we add our new artefacts.
            - config: :class:`fab.config.Config`, where we can access runtime config, such as workspace
                      and multiprocessing flags.

        Subclasses should be sure to describe their input and output artefacts.

        For the duration of this run, the given config will be available to all our methods as `self._config`.
        This is useful for multiprocessing steps, where it's cleanest to pass a list of artifacts through a function.
        In this case, we don't want to also pass the config, so setting it here makes it available to all our methods.
        Because it's a runtime attribute, we don't show it in the constructor. (Discuss?)

        """
        self._config = config

    def run_mp(self, items, func):
        """
        Like run(), but uses multiprocessing to process multiple items at once.

        """
        if self._config.use_multiprocessing:
            with multiprocessing.Pool(self._config.n_procs) as p:
                results = p.map(func, items)
        else:
            results = [func(f) for f in items]

        return results

    def run_mp_imap(self, items, func, result_handler):
        """
        Like run_mp, but uses imap instead of map so that we can process each result as it happens.

        This is useful, for example, for a time consuming process where we want to save our progress as we go
        instead of waiting for everything to finish, allowing us to pick up where we left off in the program is halted.

        """
        if self._config.use_multiprocessing:
            with multiprocessing.Pool(self._config.n_procs) as p:
                # We use imap because we want to save progress as we go
                analysis_results = p.imap_unordered(func, items)
                result_handler(analysis_results)
        else:
            analysis_results = (func(a) for a in items)  # generator
            result_handler(analysis_results)

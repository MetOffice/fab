##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A helper step to copy .inc files to the root of the build source folder, for easy include by the preprocessor.

Currently only used for building JULES, .inc files are due to be removed from dev practices,
at which point this step should be deprecated.

"""
import logging
import shutil
import warnings
from pathlib import Path

from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import suffix_filter

logger = logging.getLogger(__name__)


class RootIncFiles(Step):

    def __init__(self, name="root inc files"):
        super().__init__(name)

    def run(self, artefact_store, config):
        """
        Copy inc files into the workspace output root.

        Checks for name clash. This step does not create any artefacts.
        It's up to the user to configure other tools to find these files.

        :param artefact_store:
            Artefacts created by previous Steps.
            This is where we find the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        # todo: make the build output path a getter calculated in the config?
        build_output: Path = config.source_root.parent / BUILD_OUTPUT
        build_output.mkdir(parents=True, exist_ok=True)

        warnings.warn("RootIncFiles is deprecated as .inc files are due to be removed.", DeprecationWarning)

        # inc files all go in the root - they're going to be removed altogether, soon
        inc_copied = set()
        for fpath in suffix_filter(artefact_store["all_source"], [".inc"]):

            # don't copy from the output root to the output root!
            # this is currently unlikely to happen but did in the past, and caused problems.
            if fpath.parent == build_output:
                continue

            # check for name clash
            if fpath.name in inc_copied:
                raise FileExistsError(f"name clash for inc file: {fpath}")

            logger.debug(f"copying inc file {fpath}")
            shutil.copy(fpath, build_output)
            inc_copied.add(fpath.name)

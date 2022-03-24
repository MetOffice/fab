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
from pathlib import Path
from typing import Optional

from fab.constants import BUILD_OUTPUT
from fab.steps import Step
from fab.util import suffix_filter

logger = logging.getLogger(__name__)


class RootIncFiles(Step):

    def __init__(self, source_root: Path, build_output: Optional[Path] = None, name="root inc files"):
        super().__init__(name)
        self.source_root = source_root
        self.build_output = build_output or source_root.parent / BUILD_OUTPUT

    def run(self, artefacts, config):
        """
        Copy inc files into the workspace output root.

        Checks for name clash. This step does not create any artefacts.
        It's up to the user to configure other tools to find these files.

        """
        super().run(artefacts, config)

        # inc files all go in the root - they're going to be removed altogether, soon
        inc_copied = set()
        for fpath in suffix_filter(artefacts["all_source"], [".inc"]):

            # don't copy from the output root to the output root!
            # (i.e ancillary files from a previous run)
            if fpath.parent == self.build_output:
                continue

            # check for name clash
            if fpath.name in inc_copied:
                raise RuntimeError(f"name clash for inc file: {fpath}")

            logger.debug(f"copying inc file {fpath}")
            shutil.copy(fpath, self.build_output)
            inc_copied.add(fpath.name)

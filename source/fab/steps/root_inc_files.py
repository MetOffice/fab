##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
A helper step to copy include files to the root of the build source folder,
for easy include by the preprocessor.
"""

import logging
from pathlib import Path
import shutil
from typing import List, Optional, Union

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps import step
from fab.util import suffix_filter

logger = logging.getLogger(__name__)


@step
def root_inc_files(config: BuildConfig,
                   suffix_list: Optional[Union[List[str], str]] = None):

    """
    Copy include files with a specific suffix into the workspace
    output root.

    Checks for name clash. This step does not create any artefacts,
    nor does it add a search path. It is up to the user to configure
    other tools to find these files.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can
        read settings such as the project workspace folder or the
        multiprocessing flag.
    :param suffix_list:
        List of all suffixes to be copied (or a single suffix as string).
        Note that the `.` MUST be included (e.g. `.h90`). Defaults to `.inc`

    """

    build_output: Path = config.build_output
    build_output.mkdir(parents=True, exist_ok=True)

    if not suffix_list:
        # Keep the old default
        suffix_list = [".inc"]
    elif isinstance(suffix_list, str):
        # Convert string to a single-element list
        suffix_list = [suffix_list]

    # All include files go in the root
    inc_copied = set()
    initial_source = config.artefact_store[ArtefactSet.INITIAL_SOURCE_FILES]
    for fpath in suffix_filter(initial_source, suffix_list):
        # Do not copy from the output root to the output root!
        # This is currently unlikely to happen but did in the past,
        # and caused problems.
        if fpath.parent == build_output:
            continue

        # Check for name clash
        if fpath.name in inc_copied:
            raise FileExistsError(f"name clash for include file: {fpath}")

        logger.debug(f"copying include file {fpath}")
        shutil.copy(fpath, build_output)
        inc_copied.add(fpath.name)

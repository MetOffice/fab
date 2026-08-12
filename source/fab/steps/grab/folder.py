# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

"""
This file contains the grab_folder function.
"""
import logging
from pathlib import Path
from typing import Union

from fab.steps import step
from fab.steps.grab.files import grab_files

logger = logging.getLogger(__name__)


def grab_folder(config, src: Union[Path, str], dst_label: str = ''):
    """
    Copy a source folder to the project workspace. This function is
    deprecated, use `grab_files` instead.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param src:
        The source directory or file to grab.
    :param dst_label:
        The name of a sub folder, in the project workspace, in which to put the source.
        If not specified, the code is copied into the root of the source folder.

    """
    logger.warning("Using deprecated `grab_folder`. Use `grab_files` instead.")
    grab_files(config, src, dst_label)

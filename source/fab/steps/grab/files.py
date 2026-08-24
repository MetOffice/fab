# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

"""
This file contains the grab_files function.
"""

from pathlib import Path
from typing import Union

from fab.steps import step
from fab.tools.category import Category


@step
def grab_files(config, src: Union[Path, str], dst_label: str = ''):
    """
    Copy a source file or folder to the project workspace.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read
        settings such as the project workspace folder or the multiprocessing
        flag.
    :param src:
        The source location to grab. Either a directory or a file.
    :param dst_label:
        The name of a sub folder, in the project workspace, in which to put
        the source. If not specified, the code is copied into the root of the
        source folder.

    """
    dst = config.source_root / dst_label
    dst.mkdir(parents=True, exist_ok=True)
    rsync = config.tool_box.get_tool(Category.RSYNC)
    rsync.execute(src=Path(src), dst=dst)

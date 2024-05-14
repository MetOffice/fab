# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Union

from fab.steps import step
from fab.tools import Categories


@step
def grab_folder(config, src: Union[Path, str], dst_label: str = ''):
    """
    Copy a source folder to the project workspace.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param src:
        The source location to grab. The nature of this parameter is depends on the subclass.
    :param dst_label:
        The name of a sub folder, in the project workspace, in which to put the source.
        If not specified, the code is copied into the root of the source folder.

    """
    _dst = config.source_root / dst_label
    _dst.mkdir(parents=True, exist_ok=True)
    rsync = config.tool_box[Categories.RSYNC]
    rsync.execute(src=src, dst=_dst)

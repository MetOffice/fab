# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil
from pathlib import Path
from typing import Union

from fab.steps import step


@step
def grab_archive(config, src: Union[Path, str], dst_label: str = ''):
    """
    Copy source from an archive into the project folder.

    :param src:
        The source archive to grab from.
    :param dst_label:
        The name of a sub folder, in the project workspace, in which to put the source.
        If not specified, the code is copied into the root of the source folder.
    :param name:
        Human friendly name for logger output, with sensible default.

    """
    dst: Path = config.source_root / dst_label
    dst.mkdir(parents=True, exist_ok=True)

    shutil.unpack_archive(src, dst)

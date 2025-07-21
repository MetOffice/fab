# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from inspect import signature
from pathlib import Path
from shutil import unpack_archive
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

    # The filtering was added at v3.12 so this check may be removed once we
    # nolonger support earlier versions. It must be specified as default
    # behaviour of the filter changes at v3.14.
    #
    unpack_archive_sig = signature(unpack_archive)
    if 'filter' in unpack_archive_sig.parameters:
        #
        # The "data" filter does a number of things including disallowing
        # symlinks. It also does not recreate ownership or permissions from
        # the archive.
        #
        unpack_archive(src, dst, filter='data')
    else:
        unpack_archive(src, dst)

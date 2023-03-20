# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil
from pathlib import Path
from typing import Dict, Optional, Union

from fab.steps.grab import GrabSourceBase


class GrabArchive(GrabSourceBase):
    """
    Copy source from an archive into the project folder.

    """
    def __init__(self, src: Union[Path, str], dst: Optional[str] = None, name=None):
        """
        :param src:
            The source archive to grab from.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src=str(src), dst=dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        dst: Path = config.source_root / self.dst_label
        dst.mkdir(parents=True, exist_ok=True)

        shutil.unpack_archive(self.src, dst)

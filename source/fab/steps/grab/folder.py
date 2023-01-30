# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Union, Optional, Dict

from fab.steps.grab import GrabSourceBase, call_rsync


class GrabFolder(GrabSourceBase):
    """
    Copy a source folder to the project workspace.

    """

    def __init__(self, src: Union[Path, str], dst: Optional[str] = None, name=None):
        """
        :param src:
            The source location to grab. The nature of this parameter is depends on the subclass.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src=str(src), dst=dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        self._dst.mkdir(parents=True, exist_ok=True)  # type: ignore
        call_rsync(src=self.src, dst=self._dst)  # type: ignore

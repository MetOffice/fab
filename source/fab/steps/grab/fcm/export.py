# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Optional, Dict

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


class FcmExport(GrabSourceBase):
    """
    Export an FCM repo folder to the project workspace.

    """
    def __init__(self, src: str, dst: Optional[str] = None, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`. Can include the revision.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3'.
        :param name:
            Human friendly name for logger output, with sensible default.

        Example:

            FcmExport(src='fcm:jules.xm_tr/src', revision=revision, dst='src')

        """
        super().__init__(src, dst, name=name or f'{self.__class__.__name__} {dst} {revision}'.strip())
        self.revision = revision

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # todo: should we wipe the destination first?

        src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', src, str(config.source_root / self.dst_label)])

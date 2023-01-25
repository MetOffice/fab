# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Optional, Dict

from fab.steps.grab.fcm import GrabFcmBase
from fab.tools import run_command


class FcmExport(GrabFcmBase):
    """
    Export an FCM repo folder to the project workspace.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        dst: Path = config.source_root / self.dst_label

        # todo: should we wipe the destination first, like FcmCheckout?

        # src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', '--revision', self.revision, self.src, str(dst)])

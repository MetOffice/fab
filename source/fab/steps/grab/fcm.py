# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


class GrabFcm(GrabSourceBase):
    """
    Grab an FCM repo folder to the project workspace.

    Example:

        GrabFcm(src='fcm:jules.xm_tr/src', revision=revision, dst='src')

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', src, str(self._dst)])

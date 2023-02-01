# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

from fab.steps.grab.svn import GrabSvnBase
from fab.tools import run_command


class SvnExport(GrabSvnBase):
    """
    Export an FCM repo folder to the project workspace.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        run_command([
            self.command, 'export', '--force',
            *self._cli_revision_parts(),
            self.src,
            str(self._dst)
        ])

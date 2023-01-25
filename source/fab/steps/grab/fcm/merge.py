# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Dict

from fab.steps.grab.fcm import is_working_copy, GrabFcmBase
from fab.tools import run_command


class FcmMerge(GrabFcmBase):
    """
    Merge an FCM repo into a local working copy.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        dst: Path = config.source_root / self.dst_label

        if not dst.exists() or not is_working_copy(dst):
            raise ValueError(f"destination is not a working copy: '{dst}'")
        else:
            run_command(['fcm', 'update', '--revision', self.revision], cwd=dst)

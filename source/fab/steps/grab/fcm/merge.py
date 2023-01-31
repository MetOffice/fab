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

        if not self._dst or not is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")
        else:
            # We seem to need the url and version combined for this operation.
            # The help for fcm merge says it accepts the --revision param, like other commands,
            # but it doesn't seem to be recognised.
            rev_url = f'{self.src}'
            if self.revision is not None:
                rev_url += f'@{self.revision}'

            res = run_command(['fcm', 'merge', '--non-interactive', rev_url], cwd=self._dst)

            # Fcm doesn't return an error code when there's a conflict, so we have to scan the output.
            if 'Summary of conflicts:' in res:
                raise RuntimeError(f'fcm merge encountered a conflict(s):\n{res}')

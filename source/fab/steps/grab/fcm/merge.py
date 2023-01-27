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

        dst: Path = self._dst(config)

        if not dst.exists() or not is_working_copy(dst):
            raise ValueError(f"destination is not a working copy: '{dst}'")
        else:
            # run_command(['fcm', 'merge', *self._cli_revision_parts(), self.src, str(dst)])

            # we seem to need the url and version combined for this operation
            rev_url = f'{self.src}'
            if self.revision is not None:
                rev_url += f'@{self.revision}'

            # run_command(['fcm', 'merge', self.src, str(dst)])
            res = run_command(['fcm', 'merge', '--non-interactive', self.src], cwd=dst)
            print(res)

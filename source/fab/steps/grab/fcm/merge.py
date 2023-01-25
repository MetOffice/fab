# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Dict

from fab.steps.grab import GrabSourceBase
from fab.steps.grab.fcm import is_working_copy
from fab.tools import run_command


class FcmMerge(GrabSourceBase):
    """
    Merge an FCM repo into a local working copy.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None):
        # Pull out the revision if it's part of the url.
        # We need it separate from the url in case we do an update.
        url_revision = None
        at_split = src.split('@')
        if len(at_split) == 2:
            url_revision = at_split[1]
            if url_revision and revision and url_revision != revision:
                raise ValueError('Conflicting revisions in url and argument. Please provide as argument only.')
            src = at_split[0]
        else:
            assert len(at_split) == 1
        self.revision = revision or url_revision

        name = name or f'Fcm Checkout {dst} {self.revision}'.strip()
        super().__init__(src, dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        dst: Path = config.source_root / self.dst_label

        if not dst.exists() or not is_working_copy(dst):
            raise ValueError(f"destination is not a working copy: '{dst}'")
        else:
            run_command(['fcm', 'update', '--revision', self.revision], cwd=dst)

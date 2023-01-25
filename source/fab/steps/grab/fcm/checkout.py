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


class FcmCheckout(GrabSourceBase):
    """
    Checkout or update an FCM repo.

    .. note::
        If the destination is a working copy, it will be updated to the given revision, **ignoring the source url**.
        As such, the revision should be provided via the argument, not as part of the url.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None, clean=False):
        """
        :param clean:
            Wipe the destination folder first.

        """
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

        self.clean = clean

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # What's the destination? Clean it first?
        dst: Path = config.source_root / self.dst_label
        if self.clean:
            assert str(dst).startswith(str(config.source_root))
            dst.unlink()

        if not dst.exists():
            # new folder, so just checkout
            src = f'{self.src}@{self.revision}' if self.revision else self.src
            run_command(['fcm', 'checkout', '--revision', self.revision, src, str(dst)])
        else:
            # is it a working copy?
            if is_working_copy(dst):
                # update
                # todo: ensure the existing checkout is from self.src?
                run_command(['fcm', 'update', '--revision', self.revision], cwd=dst)
            else:
                # something's wrong, we can't deal with an existing folder that isn't a working copy
                raise ValueError(f"destination exists but is not an fcm working copy: '{dst}'")

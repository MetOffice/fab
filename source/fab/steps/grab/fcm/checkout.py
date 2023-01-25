# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Dict

from fab.steps.grab.fcm import is_working_copy, GrabFcmBase
from fab.tools import run_command


class FcmCheckout(GrabFcmBase):
    """
    Checkout or update an FCM repo.

    .. note::
        If the destination is a working copy, it will be updated to the given revision, **ignoring the source url**.
        As such, the revision should be provided via the argument, not as part of the url.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None, clean=False):
        """
        Params as for :class:`~fab.steps.grab.fcm.GrabFcmBase`, plus:

        :param clean:
            Wipe the destination folder first.

        """
        super().__init__(src, dst, revision=revision, name=name)
        self.clean = clean

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # What's the destination? Clean it first?
        dst: Path = config.source_root / self.dst_label
        if self.clean:
            assert str(dst).startswith(str(config.source_root))
            dst.unlink()

        # new folder?
        if not dst.exists():
            # checkout
            src = f'{self.src}@{self.revision}' if self.revision else self.src
            run_command(['fcm', 'checkout', '--revision', self.revision, src, str(dst)])
        else:
            # working copy?
            if is_working_copy(dst):
                # update
                # todo: ensure the existing checkout is from self.src?
                run_command(['fcm', 'update', '--revision', self.revision], cwd=dst)
            else:
                # we can't deal with an existing folder that isn't a working copy
                raise ValueError(f"destination exists but is not an fcm working copy: '{dst}'")

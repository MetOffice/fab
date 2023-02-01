# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

from fab.steps.grab.svn import GrabSvnBase
from fab.tools import run_command


class SvnCheckout(GrabSvnBase):
    """
    Checkout or update an FCM repo.

    .. note::
        If the destination is a working copy, it will be updated to the given revision, **ignoring the source url**.
        As such, the revision should be provided via the argument, not as part of the url.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # new folder?
        if not self._dst.exists():  # type: ignore
            run_command([
                self.command, 'checkout',
                *self._cli_revision_parts(),
                self.src, str(self._dst)
            ])

        else:
            # working copy?
            if self._is_working_copy(self._dst):  # type: ignore
                # update
                # todo: ensure the existing checkout is from self.src?
                run_command([self.command, 'update', *self._cli_revision_parts()], cwd=self._dst)  # type: ignore
            else:
                # we can't deal with an existing folder that isn't a working copy
                raise ValueError(f"destination exists but is not an fcm working copy: '{self._dst}'")

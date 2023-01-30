# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

try:
    import svn  # type: ignore
except ImportError:
    svn = None

from fab.steps.grab import GrabSourceBase


class GrabSvn(GrabSourceBase):
    """
    Grab an SVN repo folder to the project workspace.

    You can include a branch in the URL, for example:

        GrabSvn(
            src='https://code.metoffice.gov.uk/svn/lfric/GPL-utilities/trunk',
            revision=36615, dst='gpl_utils')

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        if not svn:
            raise ImportError('svn not installed, unable to continue')

        r = svn.remote.RemoteClient(self.src)
        r.export(str(self._dst), revision=self.revision, force=True)

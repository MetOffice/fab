# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from typing import Dict

try:
    import svn  # type: ignore
    from svn import remote  # type: ignore
except ImportError:
    svn = None

from fab.steps.grab import GrabSourceBase

if svn:
    class GrabSvn(GrabSourceBase):
        """
        Grab an SVN repo folder to the project workspace.

        """
        def __init__(self, src, dst=None, revision=None, name=None):
            """
            :param src:
                Repo url.
            :param dst:
                The name of a sub folder, in the project workspace, in which to put the source.
                If not specified, the code is copied into the root of the source folder.
            :param revision:
                E.g 36615
            :param name:
                Human friendly name for logger output, with sensible default.

            Example:

                GrabSvn(src='https://code.metoffice.gov.uk/svn/lfric/GPL-utilities/trunk',
                           revision=36615, dst='gpl_utils')

            """
            super().__init__(src, dst, name)
            self.revision = revision

        def run(self, artefact_store: Dict, config):
            super().run(artefact_store, config)

            r = remote.RemoteClient(self.src)
            r.export(str(config.source_root / self.dst_label), revision=self.revision, force=True)

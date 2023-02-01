# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from abc import ABC
from pathlib import Path
from typing import Union, Dict, Tuple

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


def _get_revision(src, revision=None) -> Tuple[str, Union[str, None]]:
    """
    Pull out the revision if it's part of the url.

    Some operations need it separated from the url,
    e.g. when calling fcm update, which accepts revision but no url.

    :param src:
        Repo url.
    :param revision:
        Optional revision.
    Returns (src, revision)

    """
    url_revision = None
    at_split = src.split('@')
    if len(at_split) == 2:
        url_revision = at_split[1]
        if url_revision and revision and url_revision != revision:
            raise ValueError('Conflicting revisions in url and argument. Please provide as argument only.')
        src = at_split[0]
    else:
        assert len(at_split) == 1

    return src, revision or url_revision


class GrabSvnBase(GrabSourceBase, ABC):
    """
    Base class for SVN or FCM operations.

    Mainly deals with pulling out the revision number from url and/or param.

    """

    command = 'svn'

    def __init__(self, src: str, dst: str, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`. Can end with "@rev".
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3'.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        # pull the revision out of the url, if it's in there
        src, revision = _get_revision(src, revision)
        name = name or f'{self.__class__.__name__} {dst} {revision}'.strip()
        super().__init__(src, dst, name=name, revision=revision)

    def run(self, artefact_store: Dict, config):
        if not self.tool_available:
            raise RuntimeError(f"command line tool not available: '{self.command}'")
        super().run(artefact_store, config)

    @classmethod
    def tool_available(cls) -> bool:
        """Is the command line tool available?"""
        try:
            run_command([cls.command, 'help'])
        except FileNotFoundError:
            return False
        return True

    def _cli_revision_parts(self):
        # return the command line argument to specif the revision, if there is one
        return ['--revision', str(self.revision)] if self.revision is not None else []

    def _is_working_copy(self, dst: Union[str, Path]) -> bool:
        # is the given path is a working copy?
        try:
            run_command([self.command, 'info'], cwd=dst)
        except RuntimeError:
            return False
        return True

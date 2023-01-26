# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from abc import ABC
from pathlib import Path
from typing import Union, Dict, Tuple

from fab.steps.grab import GrabSourceBase

from fab.steps import Step
from fab.tools import run_command


def is_working_copy(dst: Union[str, Path]) -> bool:
    try:
        run_command(['svn', 'info'], cwd=dst)
    except RuntimeError:
        return False
    return True


def _get_revision(src, revision=None) -> Tuple[str, str]:
    """
    Pull out the revision if it's part of the url.

    Some operations need it separated from the url,
    e.g. when calling fcm update, which accepts revision but no url.

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


class GrabFcmBase(GrabSourceBase, ABC):
    """
    Base class for FCM operations.

    Mainly deals with pulling out the revision number from url and/or param.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`. Can include the revision.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3'.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        # get source without the url and revision from the url or param
        src, self.revision = _get_revision(src, revision)
        name = name or f'{self.__class__.__name__} {dst} {self.revision}'.strip()
        super().__init__(src, dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

    def _cli_revision_parts(self):
        # return the command line argument to specif the revision, if there is one
        return ['--revision', str(self.revision)] if self.revision is not None else []

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
        if not self.tool_available():
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


class SvnExport(GrabSvnBase):
    """
    Export an FCM repo folder to the project workspace.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        run_command([
            self.command, 'export', '--force',
            *self._cli_revision_parts(),
            self.src,
            str(self._dst)
        ])


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


class SvnMerge(GrabSvnBase):
    """
    Merge an FCM repo into a local working copy.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        if not self._dst or not self._is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")
        else:
            # We seem to need the url and version combined for this operation.
            # The help for fcm merge says it accepts the --revision param, like other commands,
            # but it doesn't seem to be recognised.
            rev_url = f'{self.src}'
            if self.revision is not None:
                rev_url += f'@{self.revision}'

            res = run_command([self.command, 'merge', '--non-interactive', rev_url], cwd=self._dst)

            # Fcm doesn't return an error code when there's a conflict, so we have to scan the output.
            if 'Summary of conflicts:' in res:
                raise RuntimeError(f'fcm merge encountered a conflict(s):\n{res}')

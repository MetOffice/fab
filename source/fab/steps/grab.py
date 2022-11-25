##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Build steps for pulling source code from remote repos and local folders.

"""
import logging
import os
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Union, Optional

try:
    import svn  # type: ignore
    from svn import remote  # type: ignore
except ImportError:
    svn = None

from fab.steps import Step
from fab.util import run_command


logger = logging.getLogger(__name__)


class GrabSourceBase(Step, ABC):
    """
    Base class for source grab steps.

    Unlike most steps, grab steps don't need to read or create artefact collections.

    At runtime, when the build config is available, the destination folder is stored into `self._dst`.

    """
    def __init__(self, src: str, dst: Optional[str] = None, revision=None, shallow: bool = True, name=None):
        """
        :param src:
            The source url to grab.
        :param dst:
            The name of a sub folder in the project workspace's source folder, in which to put this source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3' or 36615
        :param shallow:
            This flag causes the grab to be quick and shallow.
            This can be faster for builds which start with an empty project folder.
            If you project folder is persistent, it can be faster to turn this flag off,
            allowing the source control software to only fetch changes since the last run.
        :param name:
            Human friendly name for logger output, with a sensible default.

        """
        super().__init__(name=name or f'{self.__class__.__name__} {src} {revision}'.strip())
        self.src: str = src
        self.dst_label: str = dst or ''
        self.revision = revision
        self.shallow = shallow

        # runtime
        self._dst: Optional[Path] = None

    @abstractmethod
    def run(self, artefact_store: Dict, config):
        """
        Perform the source grab. Called by Fab at runtime.

        :param artefact_store:
            The artefact store is where steps read and create new artefacts.
            Uncommonly, grab steps neither read nor write here.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)
        if not config.source_root.exists():
            config.source_root.mkdir(parents=True, exist_ok=True)

        self._dst = config.source_root / self.dst_label


# todo: checkout operation might be quicker for some use cases, add an option for this?
class GrabFcm(GrabSourceBase):
    """
    Grab an FCM repo folder to the project workspace.

    Example:

        GrabFcm(src='fcm:jules.xm_tr/src', revision=revision, dst='src')

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', src, str(self._dst)])


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

        r = remote.RemoteClient(self.src)
        r.export(str(self._dst), revision=self.revision, force=True)


class GrabGit(GrabSourceBase):
    """
    Grab a Git repo into the project workspace.

    If no revision is specified we'll get the default branch *if there is one*.

    .. note::

        Some git servers do not have a default branch.

        Omitting the revision is **potentially unsafe** when rebuilding with a persistent workspace
        because Fab will have to discover the current branch and update it.
        It's possible for someone to change the branch between builds.


    * It is considered unsafe to omit the revision because the checked out branch could change outside Fab.
    * If no revision is specified, there *may* be a default branch which will be grabbed, e.g for GithHub repos.
    * If a revision is specified, it should be a branch or tag.
      * If `shallow` is not set the revision can also be a commit hash.
    * If `shallow` is set (the default), only the given branch or tag is fetched, with no history.
      Otherwise, the full repo is cloned, which may be slower.

    Example:

        GrabGit(src='https://github.com/bblay/tiny_fortran.git', revision='v0.1b')

    """
    def __init__(self, src: str, dst: Optional[str] = None, revision=None, shallow: bool = True, name=None):
        """
        Params as for
        """
        super().__init__(src=src, dst=dst, revision=revision, shallow=shallow, name=name)
        if not self.revision:
            raise ValueError("GrabGit (currently) requires a revision to be specifed.")

    # Developers' note:
    # GitHub doesn't have uploadpack.allowReachableSHA1InWant set so we can't clone or fetch a commit.

    # hence the restriction on the revision not being a commit, with the command we use for a shallow grab.
    # When shallow is not set, we use different commands which can accept a commit.
    # Without this restriction there might not be much benefit to non-shallow checkouts at all.

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        if self.shallow:
            if not self._dst.exists():
                run_command(['git', 'clone', '--branch', self.revision, '--depth', '1', self.src, str(self._dst)])
            else:
                run_command(['git', 'fetch', 'origin', self.revision, '--depth', '1'], cwd=str(self._dst))
                run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=str(self._dst))
        else:
            if not self._dst.exists():
                run_command(['git', 'clone', self.src, str(self._dst)])
            else:
                run_command(['git', 'fetch', 'origin'], cwd=str(self._dst))

            run_command(['git', 'checkout', self.revision], cwd=str(self._dst))


# grabbing folders


class GrabFolder(GrabSourceBase):
    """
    Copy a source folder to the project workspace.

    """

    def __init__(self, src: Union[Path, str], dst: Optional[str] = None, name=None):
        """
        :param src:
            The source location to grab. The nature of this parameter is depends on the subclass.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src=str(src), dst=dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        self._dst.mkdir(parents=True, exist_ok=True)
        call_rsync(src=self.src, dst=self._dst)


class GrabPreBuild(Step):
    """
    Copy the contents of another pre-build folder into our own.

    """
    def __init__(self, path, objects=True, allow_fail=False):
        super().__init__(name=f'GrabPreBuild {path}')
        self.src = path
        self.objects = objects
        self.allow_fail = allow_fail

    def run(self, artefact_store: Dict, config):
        dst = config.prebuild_folder
        try:
            res = call_rsync(src=self.src, dst=dst)

            # log the number of files transferred
            to_print = [line for line in res.splitlines() if 'Number of' in line]
            logger.info('\n'.join(to_print))

        except RuntimeError as err:
            msg = f"could not grab pre-build '{self.src}':\n{err}"
            logger.warning(msg)
            if not self.allow_fail:
                raise RuntimeError(msg)


def call_rsync(src: Union[str, Path], dst: Union[str, Path]):
    # we want the source folder to end with a / for rsync because we don't want it to create a sub folder
    src = os.path.expanduser(str(src))
    if not src.endswith('/'):
        src += '/'

    command = ['rsync', '--times', '--stats', '-ru', src, str(dst)]
    return run_command(command)

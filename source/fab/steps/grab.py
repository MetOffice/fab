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
    def __init__(self, src: str, dst: Optional[str] = None, revision=None, name=None):
        """
        :param src:
            The source url to grab.
        :param dst:
            The name of a sub folder in the project workspace's source folder, in which to put this source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3' or 36615
        :param name:
            Human friendly name for logger output, with a sensible default.

        """
        super().__init__(name=name or f'{self.__class__.__name__} {src} {revision}'.strip())
        self.src: str = src
        self.dst_label: str = dst or ''
        self.revision = revision

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

    A destination name must be specified because each git repo needs to be in a separate folder.

    .. note::

        Currently, a revision must be specified.
        If `shallow` is set (the default), then the revision should only be a branch or tag.
        If `shallow` is not set, the revision can also be a commit hash.

    A `shallow` grab clones/fetches the given revision with no history.
    Otherwise, the full repo is cloned, including all branches and history.

    Example:

        GrabGit(src='https://github.com/bblay/tiny_fortran.git', revision='v0.1b')
        GrabGit(src='https://github.com/bblay/tiny_fortran.git', revision='a1b2c3', shallow=False)

    """

    def __init__(self, src: Union[Path, str], dst: str = None,  # type: ignore
                 revision=None, shallow: bool = True, name=None):
        """
        Params as for :class:`~fab.steps.grab.GrabSourceBase`, plus the following.

        :param shallow:
            This flag causes the grab to be quick and shallow, fetching just the branch and no history.
            You may need to turn this off when fetching a commit hash (as opposed to a branch or tag),
            depending on the git server.

        """
        if not revision:
            raise ValueError("GrabGit (currently) requires a revision to be specifed.")

        if not dst:
            raise ValueError("A destination name must be specified to GrabGit.")

        super().__init__(src=str(src), dst=dst, revision=revision, name=name)

        self.shallow = shallow

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        if self.shallow:
            if not self._dst.exists():  # type: ignore
                run_command(['git', 'clone', '--branch', self.revision, '--depth', '1', self.src, str(self._dst)])
            else:
                run_command(['git', 'fetch', 'origin', self.revision, '--depth', '1'], cwd=str(self._dst))
                run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=str(self._dst))
        else:
            if not self._dst.exists():  # type: ignore
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

        self._dst.mkdir(parents=True, exist_ok=True)  # type: ignore
        call_rsync(src=self.src, dst=self._dst)  # type: ignore


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

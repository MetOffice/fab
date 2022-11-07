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
    Base class for grab steps. All grab steps require a source and a folder in which to put it.

    Unlike most steps, grab steps don't need to read or create artefact collections.

    """
    def __init__(self, src: str, dst: Optional[str] = None, name=None):
        """
        :param src:
            The source location to grab. The nature of this parameter is depends on the subclass.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name=name or f'{self.__class__.__name__} {dst or src}'.strip())
        self.src: str = src
        self.dst_label: str = dst or ''

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

        dst: Path = config.source_root / self.dst_label
        dst.mkdir(parents=True, exist_ok=True)

        call_rsync(src=self.src, dst=dst)


# todo: checkout operation might be quicker for some use cases, add an option for this?
class GrabFcm(GrabSourceBase):
    """
    Grab an FCM repo folder to the project workspace.

    """
    def __init__(self, src: str, dst: Optional[str] = None, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3'
        :param name:
            Human friendly name for logger output, with sensible default.

        Example:

            GrabFcm(src='fcm:jules.xm_tr/src', revision=revision, dst='src')

        """
        super().__init__(src, dst, name=name or f'{self.__class__.__name__} {dst} {revision}'.strip())
        self.revision = revision

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', src, str(config.source_root / self.dst_label)])


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

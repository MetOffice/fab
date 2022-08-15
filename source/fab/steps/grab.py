##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Build steps for pulling source code from remote repos and local folders.

"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Union

from svn import remote  # type: ignore

from fab.steps import Step
from fab.util import run_command


class GrabBase(Step, ABC):
    """
    Base class for grab steps. All grab steps require a source and a folder in which to put it.

    Unlike most steps, grab steps don't need to read or create artefact collections.

    """
    def __init__(self, src: str, dst: str, name=None):
        """
        :param src:
            The source location to grab. The nature of this parameter is depends on the subclass.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(name=name or f'{self.__class__.__name__} {dst or src}'.strip())
        self.src: str = src
        self.dst_label: str = dst

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


class GrabFolder(GrabBase):
    """
    Copy a source folder to the project workspace.

    """

    def __init__(self, src: Union[Path, str], dst: str, name=None):
        """
        :param src:
            The source location to grab. The nature of this parameter is depends on the subclass.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src=str(src), dst=dst, name=name)

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # we want the source folder to end with a / for rsync because we don't want it to create a sub folder
        src = os.path.expanduser(self.src)
        if not src.endswith('/'):
            src += '/'

        dst: Path = config.source_root / self.dst_label
        dst.mkdir(parents=True, exist_ok=True)

        command = ['rsync', '-ruq', src, str(dst)]
        run_command(command)


# todo: checkout operation might be quicker for some use cases, add an option for this?
class GrabFcm(GrabBase):
    """
    Grab an FCM repo folder to the project workspace.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
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


class GrabSvn(GrabBase):
    """
    Grab an SVN repo folder to the project workspace.

    """
    def __init__(self, src, dst, revision=None, name=None):
        """
        :param src:
            Such as `fcm:jules.xm_tr/src`.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
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

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

from svn import remote  # type: ignore

from fab.steps import Step
from fab.util import run_command


class GrabBase(Step, ABC):
    """
    All grab steps require a source and a folder in which to put it.

    """
    def __init__(self, src, dst_label, name=None):
        """
        Args:
            - src: The source location to grab. The nature of this is depends on the subclass.
            - dst_label: The name of a sub folder in the project workspace, in which to put the source.

        """
        super().__init__(name=name or f'{self.__class__.__name__} {dst_label or src}'.strip())
        self.src: str = src
        self.dst_label: str = dst_label

    @abstractmethod
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)
        if not config.source_root.exists():
            config.source_root.mkdir(parents=True, exist_ok=True)


class GrabFolder(GrabBase):
    """
    Step to copy a source folder to the project workspace.

    """
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

    def __init__(self, src, dst_label, revision=None, name=None):
        super().__init__(src, dst_label, name=name or f'{self.__class__.__name__} {dst_label} {revision}'.strip())
        self.revision = revision

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        src = f'{self.src}@{self.revision}' if self.revision else self.src
        run_command(['fcm', 'export', '--force', src, str(config.source_root / self.dst_label)])


class GrabSvn(GrabBase):
    def __init__(self, src, dst_label, revision=None, name=None):
        super().__init__(src, dst_label, name)
        self.revision = revision

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        r = remote.RemoteClient(self.src)
        r.export(str(config.source_root / self.dst_label), revision=self.revision, force=True)

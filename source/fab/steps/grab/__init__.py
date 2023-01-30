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

from fab.steps import Step
from fab.tools import run_command

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


def call_rsync(src: Union[str, Path], dst: Union[str, Path]):
    # we want the source folder to end with a / for rsync because we don't want it to create a sub folder
    src = os.path.expanduser(str(src))
    if not src.endswith('/'):
        src += '/'

    command = ['rsync', '--times', '--stats', '-ru', src, str(dst)]
    return run_command(command)

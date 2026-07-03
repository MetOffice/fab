from pathlib import Path
from typing import Iterable, Optional

from fabengine.actions import (
    Action,
    Prerequisite,
    TwoPartPath,
)
from fabengine.artefact_store import Artefact, ArtefactPath
from fabengine.database import Database
from fabengine.prerequisite import RealFilePrerequisite


class MapFile(Action):
    """
    Maps a file into the virtual filespace.
    """

    def __init__(
        self, real_file: TwoPartPath, database: Database, tag: Optional[str] = None
    ):
        super().__init__(str(real_file.full))
        self._real_file = real_file
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return f"Map file: {self._real_file.full}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [RealFilePrerequisite(self._real_file.full)]

    @property
    def real_file(self) -> Path:
        return self._real_file.full

    @property
    def artefact(self) -> Artefact:
        if self._tag:
            virtual_filename = ArtefactPath(self._tag) / self._real_file.branch
        else:
            virtual_filename = ArtefactPath(self._real_file.branch)
        return Artefact(virtual_filename, self.real_file)

    def perform(self) -> list[Action]:
        """
        Performs the mapping.
        """
        self._database.artefact_store.map_file(
            self.real_file, self.artefact.virtual_filename
        )
        return []

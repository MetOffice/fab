from collections.abc import Iterable
from pathlib import Path

from fabengine.actions import (
    Action,
    Prerequisite,
    TwoPartPath,
)
from fabengine.artefact_store import ArtefactPath
from fabengine.database import Database
from fabengine.prerequisite import RealFilePrerequisite


class MapFile(Action):
    """
    Maps a file into the virtual filespace.
    """

    def __init__(
        self, real_file: TwoPartPath, database: Database, tag: str | None = None
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
    def real_file(self) -> TwoPartPath:
        return self._real_file

    @property
    def real_path(self) -> Path:
        return self._real_file.full

    @property
    def artefact_path(self) -> ArtefactPath:
        if self._tag:
            virtual_filename = ArtefactPath(self._tag) / self._real_file.branch
        else:
            virtual_filename = ArtefactPath(self._real_file.branch)
        return virtual_filename

    def perform(self) -> list[Action]:
        """
        Performs the mapping.
        """
        self._database.artefact_store.map_file(self.real_path, self.artefact_path)
        return []

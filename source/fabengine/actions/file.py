from pathlib import Path
from shutil import copyfile
from typing import Iterable

from fabengine.actions import Action, SubprocessActionException, Prerequisite
from fabengine.database import Database
from fabengine.prerequisite import FilePrerequisite


class ImportFile(Action):
    def __init__(self, repo_dir: Path, filename: Path, tag: str, database: Database):
        self._repo_dir = repo_dir
        self._filename = filename
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return f"Copy file: {self._repo_dir} {self._filename}"

    @property
    def repo_dir(self) -> Path:
        return self._repo_dir

    @property
    def filename(self) -> Path:
        return self._filename

    @property
    def source_file(self) -> Path:
        return self._repo_dir / self._filename

    @property
    def destination_file(self) -> Path:
        return self._database.configuration.build_dir / self._tag / self._filename

    @property
    def command(self) -> str:
        """
        Gets a human-readable representation of the action.
        """
        return f"cp {self.source_file} {self.destination_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self.source_file)]

    def perform(self) -> list[Action]:
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            copyfile(self.source_file, self.destination_file)
        except FileNotFoundError:
            raise SubprocessActionException(self, return_code=-1, command=self.command)
        return []

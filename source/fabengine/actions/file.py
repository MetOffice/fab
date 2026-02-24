from pathlib import Path
from shutil import copyfile
from typing import Iterable

from fabengine.actions import Action, SubprocessActionException, Prerequisite
from fabengine.database import Database
from fabengine.prerequisite import FilePrerequisite


class ImportFile(Action):
    """
    Copies a file into the workspace.
    """

    def __init__(self, repo_dir: Path, filename: Path, tag: str, database: Database):
        """
        :param repo_dir: Repository to copy from.
        :param filename: File to copy, relative to repository.
        :param tag: Subsection of workspace to copy file to.
        :param database: Build state and configuration.
        """
        self._repo_dir = repo_dir
        self._filename = filename
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return f"Copy file: {self._repo_dir} {self._filename}"

    @property
    def repo_dir(self) -> Path:
        """
        Gets repository filename.
        """
        return self._repo_dir

    @property
    def filename(self) -> Path:
        """
        Gets source file, relative to repository.
        """
        return self._filename

    @property
    def source_file(self) -> Path:
        """
        Gets full source filename, including repository.
        """
        return self._repo_dir / self._filename

    @property
    def destination_file(self) -> Path:
        """
        Gets full destination filename, including tag.
        """
        return self._database.configuration.build_dir / self._tag / self._filename

    @property
    def command(self) -> str:
        """
        Human-readable interpretation of the command used.
        """
        return f"cp {self.source_file} {self.destination_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Depends on source file.
        """
        return [FilePrerequisite(self.source_file)]

    def perform(self) -> list[Action]:
        """
        Performs action.

        :return: Empty list.
        """
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            copyfile(self.source_file, self.destination_file)
        except FileNotFoundError:
            raise SubprocessActionException(
                self,
                return_code=-1,
                command=self.command,
            )
        return []

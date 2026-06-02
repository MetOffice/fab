from pathlib import Path
from shutil import copyfile
from typing import Iterable

from fabengine.actions import (
    Action,
    Prerequisite,
    SubprocessActionException,
    TwoPartPath,
)
from fabengine.database import Database
from fabengine.prerequisite import FilePrerequisite


class ImportFile(Action):
    """
    Copies a file into the workspace.
    """

    def __init__(
        self, filename: TwoPartPath, tag: str, database: Database, kind="file"
    ):
        """
        :param filename: File to copy, relative part is used in working copy.
        :param tag: Subsection of workspace to copy file to.
        :param database: Build state and configuration.
        """
        super().__init__(str(filename.full))
        self._filename = filename
        self._tag = tag
        self._database = database
        self._kind = kind

    def __str__(self) -> str:
        return (
            f"Import {self._kind} <{self._filename.full}> to <{self._filename.branch}>"
        )

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Depends on source file.
        """
        return [FilePrerequisite(self._filename.full)]

    @property
    def source(self) -> Path:
        return self._filename.full

    @property
    def destination(self) -> Path:
        return self._database.script_config["paths"]["build_dir"] / self._filename.branch

    def perform(self) -> list[Action]:
        """
        Performs action.

        :return: Empty list.
        """
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            copyfile(self.source, self.destination)
        except FileNotFoundError:
            raise SubprocessActionException(
                self, return_code=-1, command=f"cp {self.source} {self.destination}"
            )
        return []

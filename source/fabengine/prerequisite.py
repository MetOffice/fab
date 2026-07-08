from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from fabengine.actions import Prerequisite
from fabengine.artefact_store import Artefact, ArtefactPath
from fabengine.database import Database


class AnalysedPrerequisite(Prerequisite):
    """
    Prerequisite on analysis of Fortran source code.
    """

    def __init__(self, module: str, database: Database):
        """
        :param module: Name of Fortran module.
        :param database: Build state and configuration.
        """
        self._module = module
        self._database = database

    def __eq__(self, other: Any):
        assert isinstance(other, AnalysedPrerequisite)
        return self._module == other._module

    def __repr__(self) -> str:
        return f"AnalysedPrerequisite({self._module})"

    def __str__(self) -> str:
        return "Prerequisite module has been analysed: " + self._module

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: True if module has been analysed.
        """
        return self._module in self._database.prerequisites


class SymbolPrerequisite(Prerequisite):
    """
    Prerequisite on symbol in database.
    """

    def __init__(self, symbol: str, database: Database):
        """
        :param symbol: Name of symbol.
        :param database: Build state and configuration.
        """
        self._symbol = symbol
        self._database = database

    def __str__(self) -> str:
        return "Prerequisite symbol has been analysed: " + self._symbol

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: True if symbol is in symbol table.
        """
        return self._symbol in self._database.symbol_table


class RealFilePrerequisite(Prerequisite):
    """
    File exists in "real" filesystem.
    """

    def __init__(self, filename: Path):
        """
        :param filename: File which is our prerequisite.
        """
        self._filename = filename

    def __repr__(self) -> str:
        return f"RealFilePrerequisite({self._filename})"

    def __str__(self) -> str:
        return f"Prerequisite real file exists: <{str(self._filename)}>"

    def __eq__(self, other) -> bool:
        """
        Equality test for FilePrerequisite.
        Allows it to be used in hashable collections, like sets.

        :param other: Object to compare with.
        :return: True if other is a FilePrerequisite with the same filename.
        """
        return (
            isinstance(other, RealFilePrerequisite)
            and self._filename == other._filename
        )

    def __hash__(self) -> int:
        """
        Hash function for FilePrerequisites.
        Allows it to be used in hashable collections, like sets.

        :return: Hash of the filename.
        """
        return hash(self._filename)

    @property
    def filename(self) -> Path:
        """
        Gets prerequisite filename.
        """
        return self._filename

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: True if file exists.
        """
        return self._filename.exists()


class ExecutablePrerequisite(Prerequisite):
    """
    Prerequisite on file being executable.

    Also fails if the file is missing.
    """

    def __init__(self, filename: Path):
        self._filename = filename

    def __eq__(self, other: Any) -> bool:
        assert isinstance(other, ExecutablePrerequisite)
        return self._filename == other._filename

    def __repr__(self) -> str:
        return f"ExecutablePrerequisite({self._filename})"

    def __str__(self) -> str:
        return f"Prerequisite file is executable: {self._filename}"

    def ready(self) -> bool:
        if not self._filename.exists():
            return False
        meta = self._filename.stat()
        return meta.st_mode & stat.S_IEXEC > 0


class ArtefactPrerequisite(Prerequisite):
    """
    File exists in "virtual" filesystem.
    """

    def __init__(self, filename: ArtefactPath, database: Database):
        """
        :param filename: File which is our prerequisite.
        """
        self._filename = filename
        self._database = database

    def __str__(self) -> str:
        return f"Prerequisite virtual file exists <{self._filename}>"

    def __hash__(self) -> int:
        return hash(self._filename)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, ArtefactPrerequisite)
            and other._filename == self._filename
        )

    def __lt__(self, other: Any) -> bool:
        return (
            isinstance(other, ArtefactPrerequisite) and self._filename < other._filename
        )

    @property
    def filename(self) -> Artefact:
        return self._database.artefact_store.get_artefact(self._filename)

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: True if file exists.
        """
        return self._database.artefact_store.exists(self._filename)


class BooleanPrerequisite(Prerequisite):
    """
    Prerequisite on boolean value.
    """

    def __init__(self, value: bool):
        """
        :param value: Initial state of value.
        """
        self._value = value

    def __str__(self) -> str:
        return "Prerequisite boolean: " + str(self._value)

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: Current value.
        """
        return self._value

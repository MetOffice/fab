from __future__ import annotations

from pathlib import Path

from fabengine.actions import Prerequisite
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


class FilePrerequisite(Prerequisite):
    """
    Prerequisite on file existing.
    """

    def __init__(self, filename: Path):
        """
        :param filename: File to look for.
        """
        self._filename = filename

    def __str__(self) -> str:
        return "Prerequisite file exists: " + str(self._filename)

    def __eq__(self, other) -> bool:
        """
        Equality test for FilePrerequisite.
        Allows it to be used in hashable collections, like sets.

        :param other: Object to compare with.
        :return: True if other is a FilePrerequisite with the same filename.
        """
        return isinstance(other, FilePrerequisite) and self._filename == other._filename

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


class InclusionPrerequisite(Prerequisite):
    """
    Prerequisite on inclusion file.
    """

    def __init__(self, filename: Path, database: Database):
        """
        :param filename: Inclusion file.
        :param database: Build state and configuration.
        """
        self._filename = filename
        self._database = database

    def __str__(self) -> str:
        return "Prerequisite inclusion: " + str(self._filename)

    @property
    def filename(self) -> Path:
        """
        Gets prerequisite filename.
        """
        return self._filename

    def ready(self) -> bool:
        """
        Tests prerequisite.

        :return: True if file is in inclusions list.
        """
        return self._filename in self._database.inclusions


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

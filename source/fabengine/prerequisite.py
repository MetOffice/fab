from __future__ import annotations

from pathlib import Path

from fabengine.actions import Prerequisite
from fabengine.database import Database


class AnalysedPrerequisite(Prerequisite):
    def __init__(self, module: str, database: Database):
        self._module = module
        self._database = database

    def __str__(self) -> str:
        return "Prerequisite module has been analysed: " + self._module

    def ready(self) -> bool:
        return self._module in self._database.prerequisites


class SymbolPrerequisite(Prerequisite):
    def __init__(self, symbol: str, database: Database):
        self._symbol = symbol
        self._database = database

    def __str__(self) -> str:
        return "Prerequisite symbol has been analysed: " + self._symbol

    def ready(self) -> bool:
        return self._symbol in self._database.symbol_table


class FilePrerequisite(Prerequisite):
    def __init__(self, filename: Path):
        self._filename = filename

    def __str__(self) -> str:
        return "Prerequisite file exists: " + str(self._filename)

    def ready(self) -> bool:
        return self._filename.exists()


class InclusionPrerequisite(Prerequisite):
    def __init__(self, filename: Path, database: Database):
        self._filename = filename
        self._database = database

    def __str__(self) -> str:
        return "Prerequisite inclusion: " + str(self._filename)

    @property
    def filename(self) -> Path:
        return self._filename

    def ready(self) -> bool:
        return self._filename in self._database.inclusions


class BooleanPrerequisite(Prerequisite):
    def __init__(self, value: bool):
        self._value = value

    def __str__(self) -> str:
        return "Prerequisite boolean: " + str(self._value)

    def ready(self) -> bool:
        return self._value

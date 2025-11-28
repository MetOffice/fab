from __future__ import annotations

from enum import StrEnum, auto
from multiprocessing.managers import DictProxy, ListProxy, ValueProxy
from pathlib import Path

from fabengine.manager import FabManager


class Database:
    def __init__(self, fpp_variables: dict[str, str], manager: FabManager):
        self._fpp_variables = fpp_variables
        self._optimise_queue = True

        self.prerequisites: DictProxy[str, list[PrerequisiteInfo]] = manager.dict()
        self.symbol_table: DictProxy[str, SymbolInfo] = manager.dict()
        self.config_meta_dirs: ListProxy[Path] = manager.list()
        self._processed_this_round: ValueProxy[int] = manager.Value('i', 0)
        self._processed_last_round: ValueProxy[int] = manager.Value('i', 0)

    @property
    def fpp_variables(self) -> dict[str, str]:
        return self._fpp_variables

    @property
    def optimise_queue(self) -> bool:
        return self._optimise_queue

    def reset_work_done(self) -> None:
        self._processed_last_round.set(self._processed_this_round.get())
        self._processed_this_round.set(0)

    def bump_processed_tally(self) -> None:
        self._processed_this_round.value += 1

    @property
    def processed_last_round(self) -> int:
        return self._processed_last_round.get()


class PrerequisiteType(StrEnum):
    USE = auto(),
    EXTERNAL = auto()


class PrerequisiteInfo:
    def __init__(self, name: str, nature: PrerequisiteType):
        self._name = name
        self._nature = nature

    @property
    def name(self) -> str:
        return self._name

    @property
    def nature(self) -> PrerequisiteType:
        return self._nature


class SymbolType(StrEnum):
    FUNCTION = auto(),
    MODULE = auto(),
    PROGRAM = auto(),
    SUBROUTINE = auto(),
    TYPE = auto(),
    PROCEDURE = auto()


class SymbolInfo:
    def __init__(self, name: str, nature: SymbolType, source_file: Path):
        self._name = name
        self._nature = nature
        self._source_file = source_file

    @property
    def name(self) -> str:
        return self._name

    @property
    def nature(self) -> SymbolType:
        return self._nature

    @property
    def source_file(self) -> Path:
        return self._source_file

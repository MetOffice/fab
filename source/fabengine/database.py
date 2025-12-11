from __future__ import annotations

from enum import StrEnum, auto
from multiprocessing.managers import DictProxy, ListProxy, ValueProxy
from pathlib import Path

from fabengine.manager import FabManager


# Todo: Work directory and database always passed together.
class Database:
    def __init__(self, fpp_variables: dict[str, str],
                 fc_ignore_modules: list[str], libraries: list[str],
                 field_instances: list[dict[str, str]],
                 build_tags: dict[str, list[str]],
                 tag_dirs: dict[str, list[str]],
                 manager: FabManager):
        self._fpp_variables = fpp_variables
        self._fc_ignore_modules = fc_ignore_modules
        self._libraries = libraries
        self._field_instances = field_instances
        self._build_tags = build_tags
        self._tag_dirs = tag_dirs
        self._queue_new_on_front = True
        self._use_open_mp = True

        self.prerequisites: DictProxy[str, list[PrerequisiteInfo]] = manager.dict()
        self.symbol_table: DictProxy[str, SymbolInfo] = manager.dict()
        self.config_meta_dirs: ListProxy[Path] = manager.list()
        self.inclusions: DictProxy[Path, Path] = manager.dict()
        self._processed_this_round: ValueProxy[int] = manager.Value('i', 0)
        self._processed_last_round: ValueProxy[int] = manager.Value('i', 0)

    @property
    def fpp_variables(self) -> dict[str, str]:
        return self._fpp_variables

    @property
    def fc_ignore_modules(self) -> list[str]:
        return self._fc_ignore_modules

    @property
    def libraries(self) -> list[str]:
        return self._libraries

    @property
    def field_instances(self) -> list[dict[str, str]]:
        return self._field_instances

    @property
    def build_tag_args(self) -> dict[str, list[str]]:
        return self._build_tags

    @property
    def tag_dirs(self) -> dict[str, list[str]]:
        return self._tag_dirs

    @property
    def queue_new_on_front(self) -> bool:
        return self._queue_new_on_front

    @property
    def use_open_mp(self) -> bool:
        return self._use_open_mp

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
    EXTERNAL = auto(),
    UM = auto()


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

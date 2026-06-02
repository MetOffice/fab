from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, auto
from multiprocessing.managers import DictProxy, ListProxy, ValueProxy
from pathlib import Path
from typing import Type

from fabengine.actions import Action
from fabengine.configuration_tools import WriteOnceDict
from fabengine.manager import FabManager


class Database:
    """
    Build system state and configuration.
    """

    def __init__(
        self,
        script_config: WriteOnceDict,
        build_config: WriteOnceDict,
        manager: FabManager,
    ):
        """
        :param configuration: Preprepared configuration.
        :param manager: Multiprocess shared data controller.
        """
        # Todo: Remove original configuration, and use only fab_configuration.
        self._build_config = build_config

        # Create config
        self.script_config = script_config

        self.prerequisites: DictProxy[str, list[PrerequisiteInfo]] = manager.dict()
        self.symbol_table: DictProxy[str, SymbolInfo] = manager.dict()
        self.config_meta_dirs: ListProxy[Path] = manager.list()
        self.inclusions: DictProxy[Path, Path] = manager.dict()
        self._processed_this_round: ValueProxy[int] = manager.Value("i", 0)
        self._processed_last_round: ValueProxy[int] = manager.Value("i", 0)

    @property
    def build_config(self) -> WriteOnceDict:
        """
        :return: build configuration parameters.
        """
        return self._build_config

    def reset_work_done(self) -> None:
        """
        Zeroes completed work counter.
        """
        self._processed_last_round.set(self._processed_this_round.get())
        self._processed_this_round.set(0)

    def bump_processed_tally(self) -> None:
        """
        Increments completed work counter.
        """
        self._processed_this_round.value += 1

    @property
    def processed_last_round(self) -> int:
        """
        Gets work completed last round.
        """
        return self._processed_last_round.get()


# Todo: Should be StrEnum but not available until Python 3.11
#
class PrerequisiteType(Enum):
    """
    Fortran Prerequisites come from several sources.
    """

    USE = (auto(),)
    EXTERNAL = (auto(),)
    UM = auto()


class PrerequisiteInfo:
    """
    Describes a Fortran prerequisite.
    """

    def __init__(self, name: str, nature: PrerequisiteType):
        """
        :param name: symbol depended on.
        :param nature: Source of dependency.
        """
        self._name = name
        self._nature = nature

    @property
    def name(self) -> str:
        """
        :return: Symbol name.
        """
        return self._name

    @property
    def nature(self) -> PrerequisiteType:
        """
        :return: Kind of dependency.
        """
        return self._nature


# Todo: Should be StrEnum but not available until Python 3.11
#
class SymbolType(Enum):
    """
    Symbols come in several flavours.
    """

    FUNCTION = (auto(),)
    MODULE = (auto(),)
    PROGRAM = (auto(),)
    SUBROUTINE = (auto(),)
    TYPE = (auto(),)
    PROCEDURE = auto()


class SymbolInfo:
    """
    Describes one symbol.
    """

    def __init__(self, name: str, nature: SymbolType, source_file: Path):
        """
        :param name: Symbol name.
        :param nature: Symbol kind.
        :param source_file: Symbol is declared here.
        """
        self._name = name
        self._nature = nature
        self._source_file = source_file

    @property
    def name(self) -> str:
        """
        :return: Symbol name.
        """
        return self._name

    @property
    def nature(self) -> SymbolType:
        """
        :return: Symbol kind.
        """
        return self._nature

    @property
    def source_file(self) -> Path:
        """
        :return: Symbol declaration is here.
        """
        return self._source_file


@dataclass
class ActionTiming:
    """
    Record of one action run.
    """

    action: Type[Action]
    identifier: str
    timing: timedelta

    def __hash__(self):
        return hash(self.action) + hash(self.timing)


class Performance:
    """
    Tally of performance timings.
    """

    def __init__(self, manager: FabManager):
        """
        :param manager: Multiprocess shared data controller.
        """
        self._action_log: ListProxy[ActionTiming] = manager.list()

    def log_action(self, action: Action, timing: timedelta):
        """
        Logs a timing for an action.

        :param action: Timed action.
        :param timing: Time taken for action.
        """
        self._action_log.append(ActionTiming(type(action), action.action_id, timing))

    def aggregate_action_log(self) -> dict[str, timedelta]:
        """
        Gets a summary of total time taken for each action type.
        """
        result: dict[str, timedelta] = defaultdict(timedelta)
        for item in self._action_log:
            result[item.action.__name__] += item.timing
        return dict(result)

    # Todo: We might want more granular output, which is why ActionTiming
    #       stores a unique identifier. If this is needed it will be important
    #       to take into account that some actions are repeatedly requeued. In
    #       those cases it will be important to accumulate their time.


# Todo: We may need to consider some sort of output server to stream the log to
#       disc. Possibly in buffered chunks to optimise disc access. The reason
#       would be to reduce RAM usage for builds of large code bases requiring
#       many actions.

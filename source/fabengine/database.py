from __future__ import annotations

from enum import Enum, auto
from multiprocessing.managers import DictProxy, ListProxy, ValueProxy
from pathlib import Path

from fabengine.artefact_store import ArtefactPath
from fabengine.configuration_tools import WriteOnceDict
from fabengine.manager import FabManager


class Database:
    """
    Build system state and configuration.

    Todo: Rather than hardcoding content here it should probably be defined by
          the sub-systems which need it. e.g. configuration defines the
          meta-data directories list.
    """

    def __init__(
        self,
        configuration: WriteOnceDict,
        manager: FabManager,
    ):
        """
        :param configuration: Configuration parameters.
        :param manager: Multiprocess shared data controller.
        """
        self.configuration = configuration

        build_dir = self.configuration["paths"]["build_dir"]
        self.artefact_store = manager.ArtefactStore(build_dir)  # type:ignore
        self.prerequisites: DictProxy[str, list[PrerequisiteInfo]] = manager.dict()
        self.symbol_table: DictProxy[str, SymbolInfo] = manager.dict()
        self.config_meta_dirs: ListProxy[Path] = manager.list()
        self.unit_test_data: ListProxy[str] = manager.list()

        self._processed_this_round: ValueProxy[int] = manager.Value("i", 0)
        self._processed_last_round: ValueProxy[int] = manager.Value("i", 0)

        # Todo: This list is here to track whether a source file has been
        #       tagged for compilation, in order to avoid duplicate compiles.
        #
        #       This might be replaced with metadata in the virtual filesystem.
        #
        self.compiles_enqueued: ListProxy[Path] = manager.list()

        # Todo: This list tracks which unit test data directories are being
        #       copied. It exists so tests know whether to wait on their test
        #       data.
        #
        #       It might be replaced with some improved way for tasks to
        #       communicate down the chain of actions.
        #
        self.unit_data_copies_enqueued: ListProxy[str] = manager.list()

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

    USE = auto()
    EXTERNAL = auto()
    UM = auto()
    FORCED = auto()


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

    def __hash__(self) -> int:
        return hash(self._name) + hash(self._nature)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, PrerequisiteInfo)
        return self._name == other._name and self._nature == other._nature

    def __repr__(self) -> str:
        return f"PrerequisiteInfo({self._name, self._nature})"

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

    FUNCTION = auto()
    MODULE = auto()
    PROGRAM = auto()
    SUBROUTINE = auto()
    TYPE = auto()
    PROCEDURE = auto()


class SymbolInfo:
    """
    Describes one symbol.
    """

    def __init__(self, name: str, nature: SymbolType, source_file: ArtefactPath):
        """
        :param name: Symbol name.
        :param nature: Symbol kind.
        :param source_file: Symbol is declared here.
        """
        self._name = name
        self._nature = nature
        self._source_file = source_file

    def __eq__(self, other: object):
        assert isinstance(other, SymbolInfo)
        return (
            self._name == other._name
            and self._nature == other._nature
            and self._source_file == other._source_file
        )

    def __repr__(self) -> str:
        return f"SymbolInfo({self._name}, {self._nature}, {self._source_file})"

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
    def source_file(self) -> ArtefactPath:
        """
        :return: Symbol declaration is here.
        """
        return self._source_file

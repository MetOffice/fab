from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, auto
from multiprocessing.managers import DictProxy, ListProxy, ValueProxy
from pathlib import Path
from typing import Optional, Type

from fabengine.actions import Action
from fabengine.manager import FabManager
from fabengine.package import Package


class Configuration:
    """
    Read-only parameters to direct build.
    """

    def __init__(
        self,
        work_dir: Path,
        psyclone_config: Path,
        fpp_definitions: dict[str, str],
        fc_ignore_modules: list[str],
        field_instances: list[dict[str, str]],
        build_tags: dict[str, list[str]],
        tag_dirs: dict[str, list[str]],
        inclusion_suffixes: list[str],
        packages: tuple[Package, ...],
        performance_file: Optional[Path] = None,
    ):
        """
        :param work_dir: Location of workspace used by build.
        :param psyclone_config: Location of configuration file for PSyclone.
        :param fpp_definitions: Macros to be defined for Fortran preprocessor.
        :param fc_ignore_modules: Fortran modules which should not be
                                  considered dependencies.
        :param field_instances: Template injections for fields.
        :param build_tags: Mapping between tag and compiler arguments.
        :param tag_dirs: Mapping between directory and tags.
        :param inclusion_suffixes: Filename extensions which indicate files
                                   which will be included.
        :param packages: Third party library dependencies.
        :param performance_file: Write performance timings to this file.
        """
        self._work_dir = work_dir
        self._psyclone_config = psyclone_config
        self._fpp_definitions = fpp_definitions
        self._fc_ignore_modules = fc_ignore_modules
        self._field_instances = field_instances
        self._build_tags = build_tags
        self._tag_dirs = tag_dirs
        self._inclusion_suffixes = inclusion_suffixes
        self._packages = packages
        self._performance_file = performance_file

        self._use_open_mp = True

        self._build_dir = work_dir / "build"
        self._build_dir.mkdir(parents=True, exist_ok=True)

        self._module_dir = self._build_dir / "modules"
        self._module_dir.mkdir(exist_ok=True)

    @property
    def work_dir(self) -> Path:
        """
        :return: Working directory.
        """
        return self._work_dir

    @property
    def psyclone_config(self) -> Path:
        """
        :return: PSyclone configuration file.
        """
        return self._psyclone_config

    @property
    def build_dir(self) -> Path:
        """
        :return: Directory where build occurs.
        """
        return self._build_dir

    @property
    def module_dir(self) -> Path:
        """
        :return: Directory where Fortran modules are placed.
        """
        return self._module_dir

    @property
    def fpp_definitions(self) -> dict[str, str]:
        """
        :return: Macros passed to Fortran preprocessor.
        """
        return self._fpp_definitions

    @property
    def fc_ignore_modules(self) -> list[str]:
        """
        :return: Modules to ignore during analysis.
        """
        return self._fc_ignore_modules

    @property
    def field_instances(self) -> list[dict[str, str]]:
        """
        :return: Field variants to create.
        """
        return self._field_instances

    @property
    def build_tag_args(self) -> dict[str, list[str]]:
        """
        :return: Tagged compiler argument lists.
        """
        return self._build_tags

    @property
    def tag_dirs(self) -> dict[str, list[str]]:
        """
        :return: Directory keyed tag lists.
        """
        return self._tag_dirs

    @property
    def use_open_mp(self) -> bool:
        """
        :return: Control OpenMP building.
        """
        return self._use_open_mp

    @property
    def inclusion_suffixes(self) -> list[str]:
        return self._inclusion_suffixes

    @property
    def packages(self) -> tuple[Package, ...]:
        return self._packages

    @property
    def performance_file(self) -> Optional[Path]:
        return self._performance_file


class Database:
    """
    Build system state and configuration.
    """

    def __init__(self, configuration: Configuration, manager: FabManager):
        """
        :param configuration: Preprepared configuration.
        :param manager: Multiprocess shared data controller.
        """
        self._configuration = configuration

        self.prerequisites: DictProxy[str, list[PrerequisiteInfo]] = manager.dict()
        self.symbol_table: DictProxy[str, SymbolInfo] = manager.dict()
        self.config_meta_dirs: ListProxy[Path] = manager.list()
        self.inclusions: DictProxy[Path, Path] = manager.dict()
        self._processed_this_round: ValueProxy[int] = manager.Value("i", 0)
        self._processed_last_round: ValueProxy[int] = manager.Value("i", 0)

    @property
    def configuration(self) -> Configuration:
        """
        :return: configuration parameters.
        """
        return self._configuration

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

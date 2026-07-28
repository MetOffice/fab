from abc import ABC
from collections.abc import Iterable

from fabengine.configuration_tools import WriteOnceDict
from fabengine.repository import Repository


class BuildScript(ABC):
    def repositories(self) -> Iterable[Repository]:
        return []

    def packages(self) -> list[str]:
        return []

    def add_configuration(
        self,
        configuration: WriteOnceDict,
    ) -> None:
        pass

    def force_prerequisites(self) -> dict[str, str]:
        return {}

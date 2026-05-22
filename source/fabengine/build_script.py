from abc import ABC
from typing import Iterable

from fabengine.configuration_tools import WriteOnceDict
from fabengine.repository import Repository


class BuildScript(ABC):
    def repositories(self) -> Iterable[Repository]:
        return []

    def libraries(self) -> Iterable[str]:
        return []

    def fpp_definitions(self) -> WriteOnceDict:
        return WriteOnceDict({})

    def configuration(self) -> WriteOnceDict:
        return WriteOnceDict({})

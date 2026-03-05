from abc import ABC
from typing import Iterable

from fabengine.repository import Repository


class FabConfiguration(ABC):
    def repositories(self) -> Iterable[Repository]:
        return []

    def libraries(self) -> Iterable[str]:
        return []

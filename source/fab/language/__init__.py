# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Modules for handling different program languages appear in this package.
'''
from abc import ABC, abstractmethod
from pathlib import Path

from fab.database import WorkingState


class AnalysisException(Exception):
    pass


class Analyser(ABC):
    def __init__(self, state: WorkingState):
        self._state = state

    @abstractmethod
    def analyse(self, filename: Path) -> None:
        raise NotImplementedError('Abstract methods must be implemented')

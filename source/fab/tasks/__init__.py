# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Base classes for defining the main task units run by Fab.
'''
from abc import ABC, abstractmethod
from typing import List

from fab.artifact import Artifact


class TaskException(Exception):
    pass


class Task(ABC):
    @abstractmethod
    def run(self, artifacts: List[Artifact]) -> List[Artifact]:
        raise NotImplementedError('Abstract methods must be implemented')

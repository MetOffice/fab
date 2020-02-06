##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to main transformation
'''

from abc import ABC, abstractmethod
from typing import Sequence, List, Type, TypeVar
from pathlib import Path

T = TypeVar('T', bound='Transformation')


class Transformation(ABC):
    '''
    Runs a build operation which both operates on and produces
    one or more artifacts

    '''
    def __init__(self, source: Sequence[Path]) -> None:
        '''Setup and assign the source of this transformation'''
        self._source = source
        self._outputs = []

    @property
    def source(self) -> Sequence[Path]:
        '''Return the source artifacts for this transformation'''
        return self._source

    @property
    def outputs(self) -> Sequence[Path]:
        '''Returns the artifacts produced by this transformation'''
        return self._outputs

    @abstractmethod
    def transform(self) -> List[Type[T]]:
        '''
        Run the transformation, returning a list containing any
        other transformation objects that need to be processed.

        '''
        return []


class FortranPreprocess(Transformation):
    pass


class FortranCompile(Transformation):
    pass


class CPreprocess(Transformation):
    pass


class Psyclone(Transformation):
    pass


class pFUnit(Transformation):
    pass

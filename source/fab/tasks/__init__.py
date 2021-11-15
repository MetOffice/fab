# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
'''
Base classes for defining the main task units run by Fab.
'''
from abc import ABC, abstractmethod
from time import perf_counter
from typing import List

from fab.artifact import Artifact


class TaskException(Exception):
    pass


# todo: there's no point to this
class Task(ABC):
    @abstractmethod
    def run(self, artifact):
        raise NotImplementedError('Abstract methods must be implemented')


def timed_func(func):

    def timer_wrapper(*args, **kwargs):
        start = perf_counter()
        return func(*args, **kwargs), perf_counter() - start

    return timer_wrapper


def timed_method(meth):

    def timer_wrapper(self, *args, **kwargs):
        start = perf_counter()
        return meth(self, *args, **kwargs), perf_counter() - start

    return timer_wrapper

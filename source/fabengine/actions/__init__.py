from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from traceback import format_exception
from typing import Optional


class Prerequisite(ABC):
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError()


class Action(ABC):
    @abstractmethod
    def prerequisites(self) -> Iterable[Prerequisite]:
        raise NotImplementedError()

    @abstractmethod
    def perform(self) -> Iterable[Action]:
        raise NotImplementedError()


class WorkerException(BaseException, ABC):
    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError()


class EndOfWorkException(WorkerException):
    def describe(self) -> str:
        return "Worker finished for the day."


class ActionException(WorkerException, ABC):
    def __init__(self, action: Action):
        self._action = action

    @property
    def action(self) -> Action:
        return self._action

    def describe(self) -> str:
        return str(self._action)


class ExceptionActionException(ActionException):
    def __init__(self, action: Action, cause: Exception):
        super().__init__(action)
        self._cause = cause

    @property
    def cause(self) -> Exception:
        return self._cause

    def describe(self) -> str:
        return (super().describe() + " caused by "
                + ''.join(format_exception(self._cause))
                + '\n' + '\n'.join(format_exception(self._cause)))


class SubprocessActionException(ActionException):
    def __init__(self,
                 action: Action,
                 command: str,
                 return_code: int = 0,
                 stdout: Optional[str] = None,
                 stderr: Optional[str] = None):
        super().__init__(action)
        self._command = command
        self._return_code = return_code
        self._stdout = stdout
        self._stderr = stderr

    @property
    def return_code(self) -> int:
        return self._return_code

    # Todo: Accept list of strings straight from calling process.
    @property
    def command(self) -> str:
        return self._command

    @property
    def stdout(self) -> Optional[str]:
        return self._stdout

    @property
    def stderr(self) -> Optional[str]:
        return self._stderr

    def describe(self) -> str:
        description = super().describe() + f"({self._return_code}"
        description += "\nCommand: " + self._command
        if self._stdout:
            description += "\nStandard out: " + self._stdout
        if self._stderr:
            description += "\nStandard error: " + self._stderr
        return description
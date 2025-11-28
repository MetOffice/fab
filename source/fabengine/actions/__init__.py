from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
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
    def perform(self) -> Iterable[Action | ActionResult]:
        raise NotImplementedError()


class ActionResult:
    def __init__(self,
                 action: Action,
                 return_code: int = 0,
                 command: Optional[str] = None,
                 stdout: Optional[str] = None,
                 stderr: Optional[str] = None,
                 cause: Optional[Exception] = None):
        self._action = action
        self._return_code = return_code
        self._command = command
        self._stdout = stdout
        self._stderr = stderr
        self._cause = cause

    def __str__(self) -> str:
        return f"ActionsResult ({self._return_code}): {self._action}"

    @property
    def action(self) -> Action:
        return self._action

    @property
    def return_code(self) -> int:
        return self._return_code

    @property
    def command(self) -> Optional[str]:
        return self._command

    @property
    def stdout(self) -> Optional[str]:
        return self._stdout

    @property
    def stderr(self) -> Optional[str]:
        return self._stderr

    @property
    def cause(self) -> Optional[Exception]:
        return self._cause

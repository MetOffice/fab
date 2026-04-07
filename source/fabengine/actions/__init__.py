from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from subprocess import run, PIPE
from traceback import format_exception
from typing import Any, Optional


class TwoPartPath:
    """
    Holds a path as an absolute root and a relative branch.

    This reflects the way we have repositories containing subprojects.
    """

    def __init__(self, root: Path, branch: Path):
        """
        :param root: Absolute root path.
        :param branch: Relative branch path.
        """
        assert root.is_absolute(), f"Path <{root}> is not absolute"
        assert not branch.is_absolute(), f"Path <{branch}> is not relative"
        self._root = root
        self._branch = branch

    @property
    def root(self) -> Path:
        """
        Gets the root path.
        """
        return self._root

    @property
    def branch(self) -> Path:
        """
        Gets the branch path.
        """
        return self._branch

    @property
    def full(self) -> Path:
        """
        Gets the full root and branch path.
        """
        return self._root / self._branch


class Prerequisite(ABC):
    """
    Interface for prerequisite determination classes.
    """

    @abstractmethod
    def ready(self) -> bool:
        """
        Determines when a prerequisite is met.

        :return: True if prerequisite met.
        """
        raise NotImplementedError()


class Action(ABC):
    """
    Interface for work queue actions.
    """

    def __init__(self, identifier: str):
        """
        :param identifier: Uniquely identifiers an action instance from others
                           in its class. Often an input filename.
        """
        self._id = identifier

    @property
    def action_id(self) -> str:
        return self._id

    @abstractmethod
    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: All prerequisites of the action.
        """
        raise NotImplementedError()

    @abstractmethod
    def perform(self) -> Iterable[Action]:
        """
        Performs action.

        :return: Results of running the action.
        """
        raise NotImplementedError()


class SubprocessAction(Action, ABC):
    def __init__(self, executable: Path, arguments: Optional[Iterable[Any]] = None):
        self._executable = executable
        self._arguments = arguments or []
        super().__init__(" ".join(str(self._arguments)))

    def run_subprocess(
        self, additional_arguments: Optional[Iterable[Any]] = None
    ) -> None:
        command = [str(self._executable)]

        for arg in self._arguments:
            command.append(str(arg))

        for arg in additional_arguments or []:
            command.append(str(arg))

        process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8")
        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )


class WorkerException(BaseException, ABC):
    """
    Communicates happenings to the farmer.
    """

    @abstractmethod
    def describe(self) -> str:
        """
        Describes happening to a human.
        """
        raise NotImplementedError()


class EndOfWorkException(WorkerException):
    """
    Worker has completed its work.
    """

    def describe(self) -> str:
        return "Worker finished for the day."


class ActionException(WorkerException, ABC):
    """
    Work action experienced a happening.
    """

    def __init__(self, action: Action):
        self._action = action

    @property
    def action(self) -> Action:
        """
        :return: Inciting action.
        """
        return self._action

    def describe(self) -> str:
        return str(self._action)


class ExceptionActionException(ActionException):
    """
    Work action threw an exception.
    """

    def __init__(self, action: Action, cause: Exception):
        super().__init__(action)
        self._cause = cause

    @property
    def cause(self) -> Exception:
        """
        Exception thrown by action.
        """
        return self._cause

    def describe(self) -> str:
        return (
            super().describe()
            + " caused by "
            + "".join(format_exception(self._cause))
            + "\n"
            + "\n".join(format_exception(self._cause))
        )


class SubprocessActionException(ActionException):
    """
    Work action subprocess experienced a happening.
    """

    def __init__(
        self,
        action: Action,
        command: str,
        return_code: int = 0,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(action)
        self._command = command
        self._return_code = return_code
        self._stdout = stdout
        self._stderr = stderr

    @property
    def return_code(self) -> int:
        """
        :return: Zero for success, otherwise failure.
        """
        return self._return_code

    # Todo: Accept list of strings straight from calling process.
    @property
    def command(self) -> str:
        """
        :return: Inciting command.
        """
        return self._command

    @property
    def stdout(self) -> Optional[str]:
        """
        :return: Command's standard output text.
        """
        return self._stdout

    @property
    def stderr(self) -> Optional[str]:
        """
        :return: Command's standard error text.
        """
        return self._stderr

    def describe(self) -> str:
        description = super().describe() + f"({self._return_code})"
        description += "\nCommand: " + self._command
        if self._stdout:
            description += "\nStandard out: " + self._stdout
        if self._stderr:
            description += "\nStandard error: " + self._stderr
        return description

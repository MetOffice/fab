from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from subprocess import CompletedProcess, run
from traceback import extract_stack, format_exception
from typing import Any

from fabengine.logserver import make_logger


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

    def __init__(self, identifier: str, key: object | None = None):
        """
        :param identifier: Uniquely identifiers an action instance from others
                           in its class. Often an input filename.
        """
        self._id = identifier
        self._reused = False
        self._key = key or identifier
        self._hash = hash(f"{self.__class__}.{self._key}")

    def __hash__(self) -> int:
        return self._hash

    @property
    def action_id(self) -> str:
        return self._id

    @property
    def reused(self):
        return self._reused

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
    def __init__(
        self,
        executable: Path | None = None,
        arguments: Iterable[Any] | None = None,
        identification: str | None = None,
        mpi: int | None = None,
        key: object | None = None,
    ):
        self._executable = executable
        self._arguments = arguments or []
        if mpi is None or mpi > 0:
            self._mpi = mpi
        else:  # mpi < 1
            raise ValueError("Number of MPI ranks must be 1 or greater.")
        if not identification:
            identification = (
                f"{self._executable} {' '.join(str(arg) for arg in self._arguments)}"
            )

        super().__init__(
            identification,
            key=key,
        )

    @property
    def executable(self) -> Path | None:
        return self._executable

    def run_subprocess(
        self,
        directory: Path | None = None,
        additional_arguments: Iterable[Any] | None = None,
        output=False,
    ) -> None | CompletedProcess:
        command: list[str]
        if self._mpi:
            command = ["mpiexec", "-n", str(self._mpi)]
        else:
            command = []

        if self._executable:
            command.append(str(self._executable))

        for arg in self._arguments:
            command.append(str(arg))

        for arg in additional_arguments or []:
            command.append(str(arg))

        # Check that a command has been defined
        if not command:
            logger = make_logger("system")
            logger.warning(
                (
                    "A run_subprocess action has been called, but no action defined",
                    extract_stack(),
                )
            )
            return None

        if directory:
            process = run(
                command, cwd=directory, capture_output=True, text=True, check=False
            )
        else:
            process = run(command, capture_output=True, text=True, check=False)

        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )
        if output:
            return process
        return None


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

        # Exceptions include a lot of references to Python environment state
        # and as such, cannot be pickled. Since the multiprocessing
        # library is based on pickling we need to convert the internal
        # references to a flat string at this point in order to get useful
        # backtraces out the other side.
        #
        self._backtrace = format_exception(self._cause)

    @property
    def cause(self) -> Exception:
        """
        Exception thrown by action.
        """
        return self._cause

    def describe(self) -> str:
        return super().describe() + " caused by:\n" + "".join(self._backtrace)


class SubprocessActionException(ActionException):
    """
    Work action subprocess experienced a happening.
    """

    def __init__(
        self,
        action: Action,
        command: str,
        return_code: int = 0,
        stdout: str | None = None,
        stderr: str | None = None,
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
    def stdout(self) -> str | None:
        """
        :return: Command's standard output text.
        """
        return self._stdout

    @property
    def stderr(self) -> str | None:
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

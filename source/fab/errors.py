##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Custom exception classes designed to replace generic RuntimeError
exceptions originally used in fab.
"""

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from fab.tools.category import Category
    from fab.tools.tool import Tool


class FabError(RuntimeError):
    """Base class for all fab specific exceptions.

    :param message: reason for the exception
    """

    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


class FabToolError(FabError):
    """Base class for fab tool and toolbox exceptions.

    :param tool: name of the current tool or category
    :param message: reason for the exception
    """

    def __init__(self, tool: Union["Category", "Tool", str], message: str) -> None:
        self.tool = tool

        # Check for name attributes rather than using isinstance
        # because Category and Tool have issues with circular
        # dependencies
        if hasattr(tool, "name"):
            self.name = tool.name
        else:
            self.name = tool
        super().__init__(f"[{self.name}] {message}")


class FabToolMismatch(FabToolError):
    """Tool and category mismatch.

    Error when a tool category does not match the expected setting.

    :param tool: name of the current tool
    :param category: name of the current category
    :param expectedd: name of the correct category
    """

    def __init__(
        self,
        toolname: str,
        category: Union["Category", "Tool", type],
        expected: str,
    ) -> None:
        self.category = category
        self.expected = expected

        super().__init__(toolname, f"got type {category} instead of {expected}")


class FabToolInvalidVersion(FabToolError):
    """Version format problem.

    Error when version information cannot be extracted from a specific
    tool.  Where a version pattern is available, report this as part
    of the error.

    :param tool: name of the current tool
    :param value: output from the query command
    :param expected: optional format of version string
    """

    def __init__(
        self,
        toolname: str,
        value: str,
        expected: Optional[str] = None,
    ) -> None:
        self.value = value
        self.expected = expected

        message = f"invalid version {repr(self.value)}"
        if expected is not None:
            message += f" should be {repr(expected)}"

        super().__init__(toolname, message)


class FabToolPsycloneAPI(FabToolError):
    """PSyclone API and target problem.

    Error when the specified PSyclone API, which can be empty to
    indicate DSL mode, and the associated target do not match.

    :param api: the current API or empty for DSL mode
    :param target: the name of the target
    :param present: optionally whether the target is present or
        absent.  Used to format the error message.  Defaults to False.
    """

    def __init__(
        self, api: Union[str, None], target: str, present: Optional[bool] = False
    ) -> None:
        self.target = target
        self.present = present
        self.api = api

        message = "called "
        if api:
            message += f"with {api} API "
        else:
            message += "without API "
        if present:
            message += "and with "
        else:
            message += "but not with "
        message += f"{target}"

        super().__init__("psyclone", message)


class FabToolNotAvailable(FabToolError):
    """An unavailable tool has been requested.

    Error where a tool which is not available in a particular suite of
    tools has been requested.

    :param tool: name of the current tool
    :param suite: optional name of the current tool suite
    """

    def __init__(
        self,
        tool: Union["Category", "Tool", str],
        suite: Optional[Union["Category", str]] = None,
    ) -> None:
        message = "not available"
        if suite:
            message += f" in {suite}"
        super().__init__(tool, message)


class FabToolInvalidSetting(FabToolError):
    """An invalid tool setting has been requested.

    Error where an invalid setting, e.g. MPI, has been requested for a
    particular tool.

    :param setting_type: name of the invalid setting
    :param tool: the tool to which setting applies
    :param additional: optional additional information
    """

    def __init__(
        self,
        setting_type: str,
        category: Union["Category", str],
        additional: Optional[str] = None,
    ) -> None:
        self.setting_type = setting_type

        message = f"invalid {setting_type}"
        if additional:
            message += f" {additional}"

        super().__init__(category, message)


class FabUnknownLibraryError(FabError):
    """An unknown library has been requested.

    Error where an library which is not known to the current Linker
    instance is requested.

    :param library: the name of the unknown library
    """

    def __init__(self, library: str) -> None:
        self.library = library
        super().__init__(f"unknown library {repr(library)}")


class FabCommandError(FabError):
    """An error was encountered running a subcommand.

    Error where a subcommand run by the fab framework returned with a
    non-zero exit code.  The exit code plus any data from the stdout
    and stderr streams are retained to allow them to be passed back up
    the calling stack.

    :param command: the command being run
    :param code: the command return code from the OS
    :param output: output stream from the command
    :param error: error stream from the command
    """

    def __init__(
        self,
        command: List[str],
        code: int,
        output: Union[str, bytes, None],
        error: Union[str, bytes, None],
        cwd: Optional[Union[Path, str]] = None,
    ) -> None:
        self.command: str = " ".join(command)
        self.code = int(code)
        self.output = self._decode(output)
        self.error = self._decode(error)
        self.cwd = cwd
        super().__init__(f"return code {code} from {repr(self.command)}")

    def _decode(self, value: Union[str, bytes, None]) -> str:
        """Convert from bytes to a string as necessary."""
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode()
        return value


class FabCommandNotFound(FabError):
    """Target command could not be found by subprocess.

    Error where the target command passed to a subprocess call could
    not be found.

    :param command: the target command.  For clarity, only the first
        item is used in the error message but the entire command is
        preserved for inspection by the caller.
    """

    def __init__(self, command: Union[List[str], str]) -> None:
        self.command = command
        if isinstance(command, list):
            self.target: str = command[0]
        elif isinstance(command, str):
            self.target = command.split()[0]
        else:
            raise ValueError(f"invalid command: {command}")

        super().__init__(f"unable to execute {repr(self.target)}")


class FabMultiCommandError(FabError):
    """Unpack multiple exceptions into a single one.

    Error which combines all potential exceptions raised by a
    multiprocessing section into a single exception class for
    subsequent inspection.

    This feature is required because versions of python prior to
    3.11 do not support ExceptionGroups.  See issue #513 on github.

    :param errors: a list ot exceptions
    :param label: an identifier for the multiprocessing section
    """

    def __init__(self, errors: List[Exception], label: Optional[str] = None) -> None:
        self.errors = errors
        self.label = label or "during multiprocessing"

        message = f"{len(errors)} exception"
        message += " " if len(errors) == 1 else "s "
        message += f"{self.label}"

        super().__init__(message)


class FabSourceError(FabError):
    """Base class for source code management exceptions."""


class FabSourceNoFilesError(FabSourceError):
    """No source files were found.

    Error where no source files have been once any filtering rules
    have been applied.

    """

    def __init__(self) -> None:
        super().__init__("no source files found after filtering")


class FabSourceMergeError(FabSourceError):
    """Version control merge has failed.

    Error where the underlying version control system has failed to
    automatically merge source code changes, e.g. because of a source
    conflict that requires manual resolution.

    :param tool: name of the version control system
    :param reason: reason/error output from the version control system
        indicating why the merge failed
    :param revision: optional name of the specific revision being
        targeted
    """

    def __init__(
        self, tool: "Tool", reason: str, revision: Optional[str] = None
    ) -> None:
        self.tool = tool
        self.reason = reason

        message = f"[{tool.name}] merge "
        if revision:
            message += f"of {repr(revision)} "
        message += f"failed: {reason}"

        super().__init__(message)


class FabSourceFetchError(FabSourceError):
    """An attempt to fetch source files has failed.

    Error where a specific set of files could not be fetched,
    e.g. from a location containing prebuild files.

    :params source: location of the source files
    :param reason: reason for the failure
    """

    def __init__(self, source: str, reason: str) -> None:
        self.source = source
        self.reason = reason
        super().__init__(f"could not fetch {source}: {reason}")


class FabAnalysisError(FabError):
    """Error while parsing or analysing source code."""

    def __init__(self, message, fpath=None, lineno=None):
        if fpath is not None:
            # Add the name of the source file and the line number
            message = message.rstrip() + f" ({fpath.name}"
            if lineno is not None:
                message += f":{lineno}"
            message += ")"
        super().__init__(message)


class FabFileLoadError(FabError):
    """Error loading a FabFile."""

    def __init__(self, message, fpath):
        super().__init__(message)
        self.fpath = fpath


class FabProfileError(FabError):
    """Error when an invalid profile is provided."""

    def __init__(self, message, profile):
        super().__init__(f"profile {repr(profile)} {message}")
        self.profile = profile


class FabHashError(FabError):
    """Error creating a file combination hash."""

    def __init__(self, fpath):
        super().__init__(f"failed to create hash for {fpath}")
        self.fpath = fpath

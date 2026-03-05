##############################################################################
# (c) Crown copyright 2025 Met Office. All rights reserved.
# The file LICENCE, distributed with this code, contains details of the terms
# under which the code may be used.
##############################################################################
"""
Makes use of pkg-config files to find out about libraries.
"""

from __future__ import annotations

from abc import ABC
from os import environ as os_environ
from enum import Enum
from pathlib import Path
from re import match as re_match
from subprocess import run, PIPE
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


class PackageException(Exception):
    pass


# Todo: Should be StrEnum once we retire old Python.
#
class LinkType(Enum):
    SHARED = "--shared"
    STATIC = "--static"


class CompilerArgument(ABC):
    pass


class IncludePath(CompilerArgument):
    def __init__(self, path: Path):
        self._path = path

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, IncludePath):
            raise TypeError(
                f"Cannot compare IncludePath with {type(other).__name__}"
            )
        return self._path == other._path

    def __repr__(self) -> str:
        return f"IncludePath({self._path})"

    @property
    def path(self) -> Path:
        return self._path


class VariableDefinition(CompilerArgument):
    def __init__(self, name: str, value: Optional[str] = None):
        self._name = name
        self._value = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, VariableDefinition):
            raise TypeError(
                f"Cannot compare VariableDefinition with {type(other).__name__}"
            )
        return self._name == other._name and self._value == other._value

    def __repr__(self) -> str:
        return f"VariableDefinition({self._name}, {self._value})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> Optional[str]:
        return self._value


class LinkerArgument(ABC):
    pass


class LinkerPath(LinkerArgument):
    def __init__(self, path: Path):
        self._path = path

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LinkerPath):
            raise TypeError(
                f"Cannot compare LinkerPath with {type(other).__name__}"
            )
        return self._path == other._path

    def __repr__(self) -> str:
        return f"LinkerPath({self._path})"

    @property
    def path(self) -> Path:
        return self._path


class LibraryName(LinkerArgument):
    def __init__(self, name: str):
        self._name = name

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LibraryName):
            raise TypeError(
                f"Cannot compare LibraryName with {type(other).__name__}"
            )
        return self._name == other._name

    def __repr__(self) -> str:
        return f"LibraryName({self._name})"

    @property
    def name(self) -> str:
        return self._name


class Package:
    """
    Represents a 3rd party library.

    .. todo:: Support conflicting packages.
    """

    def __init__(
        self,
        name: str,
        version: tuple[int | str, ...],
        compile_arguments: Iterable[CompilerArgument],
        link_arguments: Iterable[LinkerArgument],
    ):
        self._name = name
        self._version = version
        self._compile_arguments = tuple(compile_arguments)
        self._link_arguments = tuple(link_arguments)

    def __repr__(self) -> str:
        return f"Package({self._name}, {self._version}, {self._compile_arguments}, {self._link_arguments})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Package):
            raise TypeError(
                f"Cannot compare Package with {type(other).__name__}"
            )
        return (
            self._name == other._name
            and self._version == other._version
            and self._compile_arguments == other._compile_arguments
            and self._link_arguments == other._link_arguments
        )

    @property
    def name(self) -> str:
        """
        Gets library name.
        """
        return self._name

    @property
    def version(self) -> Tuple[Union[int, str], ...]:
        """
        Gets library version.
        """
        return self._version

    @property
    def compile_arguments(self) -> Tuple[CompilerArgument, ...]:
        """
        Gets arguments for compiler.
        """
        return self._compile_arguments

    @property
    def link_arguments(self) -> Tuple[LinkerArgument, ...]:
        """
        Gets arguments for linker.
        """
        return self._link_arguments


def partition_specification(specification: str) -> tuple[str, str, str]:
    """
    Splits a package specification into parts.

    :param specification: `pkg_config` package specification.
    :return: Three-tuple of name, operator and value. The latter two may be
             empty strings if they are not specified.
    """
    match = re_match(r"([\w-]+)\s*([<>=]*)\s*(.*)", specification)
    if match:
        return match.group(1), match.group(2), match.group(3)
    raise ValueError("Unable to parse specification: " + specification)


def pkg_config(specification: str, link_type: LinkType = LinkType.SHARED) -> Package:
    """
    Constructs Package object from details held in pkg-config files.

    Version requirement may be specified in the same way pkg-config
    understands them. i.e. =, >, <, >= and <=

    :param specification: Package name with optional version requirement.
    :param link_type: The type of link to be performed.
    :raises PackageException: A package fulfilling the specification was
            not found.
    """
    name, _, _ = partition_specification(specification)

    _call_pkg_config(specification, ["--print-errors", "--exists"])

    version_str = _call_pkg_config(specification, ["--modversion"])
    if version_str:
        version = tuple(
            [
                int(component) if component.isdigit() else component
                for component in version_str[0].split(".")
            ]
        )
    else:  # No version string
        version = tuple()

    compile_arguments: list[CompilerArgument] = []
    carg_list = _call_pkg_config(specification, ["--cflags", link_type.value])
    cstate = "base"
    while carg_list:
        carg = carg_list.pop(0)
        if not carg:
            continue

        if cstate == "base":
            if carg[:2] == "-I":
                carg_list.insert(0, carg[2:])
                cstate = "include"
            elif carg[:2] == "-D":
                carg_list.insert(0, carg[2:])
                cstate = "define"
            else:
                raise PackageException("PkgConfig returned confusing argument: " + carg)
            continue
        if cstate == "include":
            compile_arguments.append(IncludePath(Path(carg)))
            cstate = "base"
            continue
        if cstate == "define":
            var_name, _, var_value = carg.partition("=")
            compile_arguments.append(VariableDefinition(var_name, var_value or None))
            cstate = "base"
            continue

    # ToDo: It may be necessary to use --pure with static link type.
    #
    link_arguments: list[LinkerArgument] = []
    larg_list = _call_pkg_config(specification, ["--libs", link_type.value])
    lstate = "base"
    while larg_list:
        larg = larg_list.pop(0)
        if not larg:
            continue

        if lstate == "base":
            if larg[:2] == "-L":
                larg_list.insert(0, larg[2:])
                lstate = "path"
            elif larg[:2] == "-l":
                larg_list.insert(0, larg[2:])
                lstate = "library"
            else:
                raise PackageException("PkgConfig returned confusing argument: " + larg)
            continue
        if lstate == "path":
            link_arguments.append(LinkerPath(Path(larg)))
            lstate = "base"
            continue
        if lstate == "library":
            link_arguments.append(LibraryName(larg))
            lstate = "base"
            continue

    return Package(name, version, compile_arguments, link_arguments)


def _call_pkg_config(specification: str, arguments: List[str]) -> List[str]:
    environment: Dict[str, str] = {"PKG_CONFIG_DEBUG_SPEW": "YES"}
    if "PKG_CONFIG_LIBDIR" in os_environ:
        environment["PKG_CONFIG_LIBDIR"] = os_environ["PKG_CONFIG_LIBDIR"]
    if "PKG_CONFIG_PATH" in os_environ:
        environment["PKG_CONFIG_PATH"] = os_environ["PKG_CONFIG_PATH"]
    command = ["pkg-config"]
    command.extend(arguments)
    command.append(specification)
    process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8", env=environment)
    if process.returncode != 0:
        raise PackageException(f"Failed to run [{command}]: {process.stderr}")
    if process.stderr:
        raise PackageException(process.stderr)
    return process.stdout.split()

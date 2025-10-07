#!/usr/bin/env python3
##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""
Fab command line argument parser.

This extends the arparse.ArgumentParser class to ensure that specific
default arguments are added if they have not been added by the caller.

It also adds the ability to perform a two-phase parse, where the first
attempt limits itself to identifying the value of a --file option.
The idea is that if this is set, it will be used to identify a file
that contains a function which accepts an argument parser as an
argument and adds its own arguments.
"""

import argparse
import os
from pathlib import Path
from typing import Callable

from ..util import get_fab_workspace
from .. import __version__ as fab_version
from ..logtools import setup_logging


def full_path_type(opt: str) -> Path:
    """Path with expanded usernames and resolved symlinks.

    :param str opt: command line option
    :return: a fully resolved Path instance
    """

    return Path(opt).expanduser().resolve()


def _parser_wrapper(func: Callable) -> Callable:
    """Decorator to wrap arguments and checks.

    Decorator which ensures some arguments are added before the first
    of any main parser calls because they can potentially be called
    more than once.  These are added at the point where the parser is
    called to allow the user to override them.

    Always run some Namespace checks after the options have been
    parsed and then return the results.

    The decorator exists outside the class to avoid problems with
    staticmethods in python < 3.10.
    """

    def inner(self, *args, **kwargs):

        if self._setup_needed:
            # Carry out setup actions needed only once
            self._setup_needed = False
            self._add_location_group()
            self._add_output_group()
            self._add_info_group()

        result = func(self, *args, **kwargs)

        if isinstance(result, argparse.Namespace):
            # parse_args
            namespace = result
        elif isinstance(result, tuple) and isinstance(result[0], argparse.Namespace):
            # parse_known_args
            namespace = result[0]
        else:
            raise ValueError("invalid return value from wrapped function")

        # Save the name used to refer to the current program
        namespace._progname = self.prog

        self._check_fabfile(namespace)
        self._configure_logging(namespace)

        return result

    return inner


class FabArgumentParser(argparse.ArgumentParser):
    """Fab command argument parser."""

    def __init__(self, *args, **kwargs):

        self.version = kwargs.pop("version", str(fab_version))
        self.fabfile = full_path_type(kwargs.pop("fabfile", "FabFile") or "FabFile")

        if "usage" not in kwargs:
            # Default to a simplified usage line
            kwargs["usage"] = "%(prog)s [--file FILE] [options]"

        super().__init__(*args, **kwargs)

        if self.prog == "__main__.py" and kwargs.get("prog", None) is None:
            # Try to pick up a better program name from the environment
            # or just use a default string
            self.prog = os.environ.get("__PROGNAME", "fab")

        self._have_logging = False
        self._setup_needed = True

    def _add_location_group(self):
        """Add project, workspace, and fabfile args."""
        group = self.add_argument_group("fab location arguments")

        self._add_fabfile_argument(group)

        group.add_argument(
            "--project", type=str, metavar="NAME", help="name to assign to the project"
        )

        group.add_argument(
            "--workspace",
            type=full_path_type,
            metavar="DIR",
            default=get_fab_workspace().expanduser().resolve(),
            help="location of working space (default: %(default)s)",
        )

    def _add_output_group(self):
        """Add output arguments if not present."""

        # Create an output group
        group = self.add_argument_group("fab output arguments")

        if (
            "--debug" not in self._option_string_actions
            and "-d" not in self._option_string_actions
        ):
            # Add a logging option
            group.add_argument(
                "-d",
                "--debug",
                action="count",
                help="increase the amount of fab debug output",
            )

        if (
            "--verbose" not in self._option_string_actions
            and "-v" not in self._option_string_actions
        ):
            # Add a logging option
            group.add_argument(
                "-v",
                "--verbose",
                action="count",
                help="increase the amount of build output",
            )

        # Add a quiet option to suppress all/most output
        if (
            "--quiet" not in self._option_string_actions
            and "-q" not in self._option_string_actions
        ):
            # Add a logging option
            group.add_argument(
                "-q",
                "--quiet",
                action="store_true",
                help="do not produce much output",
            )

    def _add_info_group(self):
        """Add informative options."""

        # Create an info group
        group = self.add_argument_group("info arguments")

        if "--version" not in self._option_string_actions:
            group.add_argument(
                "--version", action="version", version=f"%(prog)s {self.version}"
            )

    def _configure_logging(self, namespace: argparse.Namespace) -> None:
        """Configure output logging.

        Set various logging parameters after the first complete parse
        of the command line arguments.  Check to ensure that the user
        has not attempted to set both debug and/or verbose options at
        the same time as using the --quiet flag to suppress console
        output.

        :param namespace: parsed command line arguments
        """

        if self._have_logging:
            return

        verbose = getattr(namespace, "verbose", None)
        debug = getattr(namespace, "debug", None)
        quiet = getattr(namespace, "quiet", False)

        if quiet and (verbose is not None or debug is not None):
            self.error("--quiet conflicts with debug and verbose settings")

        setup_logging(verbose, debug, quiet)

        self._have_logging = True

    def _add_fabfile_argument(self, section):
        """Add a --file argument to the target section.

        The --file argument needs to be added to both the core parser
        and to the fabfile-only parser.

        :param section: a parser or an argument section
        """

        section.add_argument(
            "--file",
            type=full_path_type,
            metavar="FILE",
            help=f"fab build script (default: {self.fabfile})",
        )

    def _check_fabfile(self, namespace: argparse.Namespace) -> None:
        """Check the fabfile status.

        If a fabfile has been specified by the user, raise an error if
        it does not exist.

        If no fabfile has been given, check the default location.  If
        it does not exist, do not raise an error, but also set the
        zero config mode.
        """

        namespace.zero_config = False

        if hasattr(namespace, "file") and namespace.file is not None:
            if not namespace.file.is_file():
                self.error(f"fab file does not exist: '{namespace.file}'")

        else:
            # Check for a default fabfile in the current directory or
            # use zero-config mode
            if self.fabfile.is_file():
                namespace.file = self.fabfile
            else:
                namespace.zero_config = True

    def parse_fabfile_only(self, *args, **kwargs):
        """Only attempt to pass the fabfile location.

        Use a separate parser instance to extract nothing but the
        --file location from the command line.  Ignore most errors and
        do not produce a help message - these should be handled by a
        second parse attempt once any additional options from the
        FabFile have been added.

        Only exit with an error if the user has provided a broken
        --file argument.

        :return: Namespace containing command line arguments
        """

        # Create a fresh parser and add the file argument
        file_only = argparse.ArgumentParser(add_help=False, exit_on_error=False)
        self._add_fabfile_argument(file_only)

        try:
            nspace, rest = file_only.parse_known_args(*args, **kwargs)
        except argparse.ArgumentError as err:
            if err.argument_name == "--file":
                # Deal with --file problems immediately
                self.error(str(err))
            nspace = argparse.Namespace(file=None, zero_config=True)

        self._check_fabfile(nspace)

        return nspace

    @_parser_wrapper
    def parse_args(self, *args, **kwargs):

        return super().parse_args(*args, **kwargs)

    @_parser_wrapper
    def parse_known_args(self, *args, **kwargs):

        return super().parse_known_args(*args, **kwargs)

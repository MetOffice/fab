##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for all tools, i.e. compiler,
preprocessor, linker, archiver, Psyclone, rsync, versioning tools.

Each tool belongs to one category (e.g. FORTRAN_COMPILER). This category
is used when adding a tool to a ToolRepository or ToolBox.
It provides basic support for running a binary, and keeping track if
a tool is actually available.
"""

import logging
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Union

from fab.tools.category import Category
from fab.tools.flags import Flags


class Tool:
    '''This is the base class for all tools. It stores the name of the tool,
    the name of the executable, and provides a `run` method.

    :param name: name of the tool.
    :param exec_name: name or full path of the executable to start.
    :param category: the Category to which this tool belongs.
    :param availability_option: a command line option for the tool to test
        if the tool is available on the current system. Defaults to
        `--version`.
    '''

    def __init__(self, name: str, exec_name: Union[str, Path],
                 category: Category = Category.MISC,
                 availablility_option: Optional[str] = None):
        self._logger = logging.getLogger(__name__)
        self._name = name
        self._exec_name = str(exec_name)
        self._flags = Flags()
        self._category = category
        if availablility_option:
            self._availability_option = availablility_option
        else:
            self._availability_option = "--version"

        # This flag keeps track if a tool is available on the system or not.
        # A value of `None` means that it has not been tested if a tool works
        # or not. It will be set to the output of `check_available` when
        # querying the `is_available` property.
        # If `_is_available` is False, any call to `run` will immediately
        # raise a RuntimeError. As long as it is still set to None (or True),
        # the `run` method will work, allowing the `check_available` method
        # to use `run` to determine if a tool is available or not.
        self._is_available: Optional[bool] = None

    def check_available(self) -> bool:
        '''Run a 'test' command to check if this tool is available in the
        system.
        :returns: whether the tool is working (True) or not.
        '''
        try:
            self.run(self._availability_option)
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    @property
    def is_available(self) -> bool:
        '''Checks if the tool is available or not. It will call a tool-specific
        function check_available to determine this, but will cache the results
        to avoid testing a tool more than once.

        :returns: whether the tool is available (i.e. installed and
            working).
        '''
        if self._is_available is None:
            self._is_available = self.check_available()
        return self._is_available

    @property
    def is_compiler(self) -> bool:
        '''Returns whether this tool is a (Fortran or C) compiler or not.'''
        return self._category.is_compiler

    @property
    def exec_name(self) -> str:
        ''':returns: the name of the executable.'''
        return self._exec_name

    @property
    def name(self) -> str:
        ''':returns: the name of the tool.'''
        return self._name

    @property
    def category(self) -> Category:
        ''':returns: the category of this tool.'''
        return self._category

    @property
    def flags(self) -> Flags:
        ''':returns: the flags to be used with this tool.'''
        return self._flags

    @property
    def logger(self) -> logging.Logger:
        ''':returns: a logger object for convenience.'''
        return self._logger

    def __str__(self):
        return f"{type(self).__name__} - {self._name}: {self._exec_name}"

    def run(self,
            additional_parameters: Optional[
                Union[str, List[Union[Path, str]]]] = None,
            env: Optional[Dict[str, str]] = None,
            cwd: Optional[Union[Path, str]] = None,
            capture_output=True) -> str:
        """
        Run the binary as a subprocess.

        :param additional_parameters:
            List of strings or paths to be sent to :func:`subprocess.run`
            as additional parameters for the command. Any path will be
            converted to a normal string.
        :param env:
            Optional env for the command. By default it will use the current
            session's environment.
        :param capture_output:
            If True, capture and return stdout. If False, the command will
            print its output directly to the console.

        :raises RuntimeError: if the code is not available.
        :raises RuntimeError: if the return code of the executable is not 0.
        """

        command = [self.exec_name] + self.flags
        if additional_parameters:
            if isinstance(additional_parameters, str):
                command.append(additional_parameters)
            else:
                # Convert everything to a str, this is useful for supporting
                # paths as additional parameter
                command.extend(str(i) for i in additional_parameters)

        # self._is_available is None when it is not known yet whether a tool
        # is available or not. Testing for `False` only means this `run`
        # function can be used to test if a tool is available.
        if self._is_available is False:
            raise RuntimeError(f"Tool '{self.name}' is not available to run "
                               f"'{command}'.")
        self._logger.debug(f'run_command: {" ".join(command)}')
        try:
            res = subprocess.run(command, capture_output=capture_output,
                                 env=env, cwd=cwd, check=False)
        except FileNotFoundError as err:
            raise RuntimeError(f"Command '{command}' could not be "
                               f"executed.") from err
        if res.returncode != 0:
            msg = (f'Command failed with return code {res.returncode}:\n'
                   f'{command}')
            if res.stdout:
                msg += f'\n{res.stdout.decode()}'
            if res.stderr:
                msg += f'\n{res.stderr.decode()}'
            raise RuntimeError(msg)
        if capture_output:
            return res.stdout.decode()
        return ""


class CompilerSuiteTool(Tool):
    '''A tool that is part of a compiler suite (typically compiler
    and linker).

    :param name: name of the tool.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite.
    :param category: the Category to which this tool belongs.
    :param mpi: whether the compiler or linker support MPI.
    '''
    def __init__(self, name: str, exec_name: Union[str, Path], suite: str,
                 category: Category, mpi: bool = False):
        super().__init__(name, exec_name, category)
        self._suite = suite
        self._mpi = mpi

    @property
    def suite(self) -> str:
        ''':returns: the compiler suite of this tool.'''
        return self._suite

    @property
    def mpi(self) -> bool:
        ''':returns: whether this tool supports MPI or not.'''
        return self._mpi

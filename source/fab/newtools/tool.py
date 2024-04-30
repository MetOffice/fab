##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This is the base class for all tools, i.e. compiler, preprocessor, linkers.
It provides basic

"""
from abc import abstractmethod
import logging
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Union

from fab.newtools.categories import Categories
from fab.newtools.flags import Flags


class Tool:
    '''This is the base class for all tools. It stores the name of the tool,
    the name of the executable, and provides a `run` method.
    '''

    def __init__(self, name: str, exec_name: str, category: Categories):
        self._logger = logging.getLogger(__name__)
        self._name = name
        self._exec_name = exec_name
        self._flags = Flags()
        self._category = category
        self._is_available: Optional[bool] = None

    @abstractmethod
    def check_available(self):
        '''An abstract method to check if this tool is available in the system.
        '''

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

    @is_available.setter
    def is_available(self, value: bool):
        '''Sets a tool to be available (i.e. installed and working)
        or not.
        :param value: if the tool is available or not.'''
        self._is_available = value

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
    def category(self) -> Categories:
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
            additional_parameters: Optional[Union[str, List[str]]] = None,
            env: Optional[Dict[str, str]] = None,
            cwd: Optional[Union[Path, str]] = None,
            capture_output=True) -> str:
        """
        Run the binary as a subprocess.

        :param additional_parameters:
            List of strings to be sent to :func:`subprocess.run` as the
            command.
        :param env:
            Optional env for the command. By default it will use the current
            session's environment.
        :param capture_output:
            If True, capture and return stdout. If False, the command will
            print its output directly to the console.

        :raises RuntimeError: if the return code of the executable is not 0.
        """

        command = [self.exec_name] + self.flags
        if additional_parameters:
            if isinstance(additional_parameters, str):
                command.append(additional_parameters)
            else:
                command.extend(additional_parameters)

        self._logger.debug(f'run_command: {" ".join(command)}')
        res = subprocess.run(command, capture_output=capture_output,
                             env=env, cwd=cwd, check=False)
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


class VendorTool(Tool):
    '''A tool that has a vendor attached to it (typically compiler
    and linker).
    '''
    def __init__(self, name: str, exec_name: str, vendor: str,
                 category: Categories):
        super().__init__(name, exec_name, category)
        self._vendor = vendor

    @property
    def vendor(self) -> str:
        '''Returns the vendor of this compiler.'''
        return self._vendor

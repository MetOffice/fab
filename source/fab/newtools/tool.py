##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This is the base class for all tools, i.e. compiler, preprocessor, linkers.
It provides basic

"""
import logging
from pathlib import Path
import subprocess
from typing import Optional, Union

from fab.newtools.categories import Categories
from fab.newtools.flags import Flags


class Tool:
    '''This is the base class for all tools. It stores the name of the tool,
    the name of the executable, and provides a `run` method.
    '''

    def __init__(self, name: str, exec_name: str, category: Categories):
        self._name = name
        self._exec_name = exec_name
        self._flags = Flags()
        self._logger = logging.getLogger(__name__)
        self._category = category

    @property
    def exec_name(self) -> str:
        return self._exec_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> Categories:
        return self._category

    @property
    def logger(self):
        return self._logger

    def __str__(self):
        return f"{type(self).__name__} - {self._name}: {self._exec_name}"

    def run(self,
            additional_parameters: Optional[Union[str, list[str]]] = None,
            env: Optional[dict[str, str]] = None,
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

        command = [self.exec_name] + self._flags.get()
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

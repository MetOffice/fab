##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains a base class for shells. This can be used to execute
other scripts.
"""

from pathlib import Path
from typing import List, Union

from fab.tools.category import Category
from fab.tools.tool import Tool


class Shell(Tool):
    '''A simple wrapper that runs a shell script. There seems to be no
    consistent way to simply check if a shell is working - not only support
    a version command (e.g. sh and dash don't). Instead, availability
    is tested by running a simple 'echo' command.

    :name: the path to the script to run.
    '''
    def __init__(self, name: str):
        super().__init__(name=name, exec_name=name,
                         availability_option=["-c", "echo hello"],
                         category=Category.SHELL)

    def exec(self, command: Union[str, List[Union[Path, str]]]) -> str:
        '''Executes the specified command.

        :param command: the command and potential parameters to execute.

        :returns: stdout of the result.
        '''
        # Make mypy happy:
        params: List[Union[str, Path]]
        if isinstance(command, str):
            params = ["-c", command]
        else:
            params = ["-c"]
            params.extend(command)
        return super().run(additional_parameters=params,
                           capture_output=True)

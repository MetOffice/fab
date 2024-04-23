# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Known command line tools whose flags we wish to manage.

"""
import logging
from pathlib import Path
import subprocess
from typing import List, Optional, Union

from fab.util import string_checksum

logger = logging.getLogger(__name__)


def flags_checksum(flags: List[str]):
    """
    Return a checksum of the flags.

    """
    return string_checksum(str(flags))


def run_command(command: List[str], env=None, cwd: Optional[Union[Path, str]] = None, capture_output=True):
    """
    Run a CLI command.

    :param command:
        List of strings to be sent to :func:`subprocess.run` as the command.
    :param env:
        Optional env for the command. By default it will use the current session's environment.
    :param capture_output:
        If True, capture and return stdout. If False, the command will print its output directly to the console.

    """
    command = list(map(str, command))
    logger.debug(f'run_command: {" ".join(command)}')
    res = subprocess.run(command, capture_output=capture_output, env=env, cwd=cwd)
    if res.returncode != 0:
        msg = f'Command failed with return code {res.returncode}:\n{command}'
        if res.stdout:
            msg += f'\n{res.stdout.decode()}'
        if res.stderr:
            msg += f'\n{res.stderr.decode()}'
        raise RuntimeError(msg)

    if capture_output:
        return res.stdout.decode()

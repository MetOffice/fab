# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Known command line tools whose flags we wish to manage.

"""
import subprocess
import warnings
from typing import Dict, List, Tuple

from fab.util import logger, string_checksum


class Compiler(object):
    """
    A command-line compiler whose flags we wish to manage.

    """
    def __init__(self, exe, compile_flag, module_folder_flag):
        self.exe = exe
        self.compile_flag = compile_flag
        self.module_folder_flag = module_folder_flag
        # We should probably extend this for fPIC, two-stage and optimisation levels.


COMPILERS: Dict[str, Compiler] = {
    'gfortran': Compiler(exe='gfortran', compile_flag='-c', module_folder_flag='-J'),
    'ifort': Compiler(exe='ifort', compile_flag='-c', module_folder_flag='-module'),
}


# todo: We're not sure we actually want to do modify incoming flags. Discuss...
# todo: this is compiler specific, rename - and do we want similar functions for other steps?
def remove_managed_flags(compiler, flags_in):
    """
    Remove flags which Fab manages.

    Fab prefers to specify a few compiler flags itself.
    For example, Fab wants to place module files in the `build_output` folder.
    The flag to do this differs with compiler.

    We don't want duplicate, possibly conflicting flags in our tool invocation so this function is used
    to remove any flags which Fab wants to manage.

    If the compiler is not known to Fab, we rely on the user to specify these flags in their config.

    .. note::

        This approach is due for discussion. It might not be desirable to modify user flags at all.

    """
    def remove_flag(flags: List[str], flag: str, len):
        while flag in flags:
            warnings.warn(f'removing managed flag {flag} for compiler {compiler}')
            flag_index = flags.index(flag)
            for _ in range(len):
                flags.pop(flag_index)

    known_compiler = COMPILERS.get(compiler)
    if not known_compiler:
        logger.warning('Unable to remove managed flags for unknown compiler. User config must specify managed flags.')
        return flags_in

    flags_out = [*flags_in]
    remove_flag(flags_out, known_compiler.compile_flag, 1)
    remove_flag(flags_out, known_compiler.module_folder_flag, 2)
    return flags_out


def flags_checksum(flags: List[str]):
    """
    Return a checksum of the flags.

    """
    return string_checksum(str(flags))


def run_command(command, env=None, cwd=None, capture_output=True):
    """
    Run a CLI command.

    :param command:
        List of strings to be sent to :func:`subprocess.run` as the command.
    :param env:
        Optional env for the command. By default it will use the current session's environment.
    :param capture_output:
        If True, capture and return stdout. If False, the command will print its output directly to the console.

    """
    logger.debug(f'run_command: {command}')
    res = subprocess.run(command, capture_output=capture_output, env=env, cwd=cwd)
    if res.returncode != 0:
        msg = f'Command failed:\n{command}'
        if res.stdout:
            msg += f'\n{res.stdout.decode()}'
        if res.stderr:
            msg += f'\n{res.stderr.decode()}'
        raise RuntimeError(msg)

    if capture_output:
        return res.stdout.decode()


def get_tool(tool_str: str = '') -> Tuple[str, List[str]]:
    """
    Get the compiler, preprocessor, etc, from the given string.

    Separate the tool and flags for the sort of value we see in environment variables, e.g. `gfortran -c`.

    Returns the tool and a list of flags.

    :param env_var:
        The environment variable from which to find the tool.

    """
    tool_split = tool_str.split()
    if not tool_split:
        raise ValueError(f"Tool not specified in '{tool_str}'. Cannot continue.")
    return tool_split[0], tool_split[1:]


# todo: add more compilers and test with more versions of compilers
def get_compiler_version(compiler: str) -> str:
    """
    Try to get the version of the given compiler.

    Expects a version in a certain part of the --version output,
    which must adhere to the n.n.n format, with at least 2 parts.

    Returns a version string, e.g '6.10.1', or empty string.

    :param compiler:
        The command line tool for which we want a version.

    """
    try:
        res = run_command([compiler, '--version'])
    except FileNotFoundError:
        raise ValueError(f'Compiler not found: {compiler}')
    except RuntimeError as err:
        logger.warning(f"Error asking for version of compiler '{compiler}': {err}")
        return ''

    # Pull the version string from the command output.
    # All the versions of gfortran and ifort we've tried follow the same pattern, it's after a ")".
    try:
        version = res.split(')')[1].split()[0]
    except IndexError:
        logger.warning(f"Unexpected version response from compiler '{compiler}': {res}")
        return ''

    # expect major.minor[.patch, ...]
    # validate - this may be overkill
    split = version.split('.')
    if len(split) < 2:
        logger.warning(f"unhandled compiler version format for compiler '{compiler}' is not <n.n[.n, ...]>: {version}")
        return ''

    # todo: do we care if the parts are integers? Not all will be, but perhaps major and minor?

    logger.info(f'Found compiler version for {compiler} = {version}')

    return version

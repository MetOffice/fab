##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and two derived
classes for gfortran and ifort

"""

from pathlib import Path
from typing import List

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Compiler(Tool):
    '''This is the base class for any compiler.
    '''

    def __init__(self, name: str, exec_name: str, category: Categories,
                 compile_flag="-c", output_flag="-o", module_folder_flag=None,
                 omp_flag=None, syntax_only_flag=None):
        super().__init__(name, exec_name, category)
        self._version = None
        self._compile_flag = compile_flag
        self._output_flag = output_flag
        self._module_folder_flag = module_folder_flag
        self._omp_flag = omp_flag
        self._syntax_only_flag = syntax_only_flag
        self._module_output_path = ""

    @property
    def has_syntax_only(self):
        return self._syntax_only_flag is not None

    def set_module_output_path(self, path):
        path = str(path)
        self._module_output_path = path

    def _remove_managed_flags(self, flags: List[str]):
        '''Removes all flags in `flags` that will be managed by FAB.
        This is atm only the module output path. The list will be
        modified in-place.

        :param flags: the list of flags from which to remove managed flags.
        '''
        i = 0
        flag_len = len(self._module_folder_flag)
        while i < len(flags):
            flag = flags[i]
            # "-J/tmp" and "-J /tmp" are both accepted.
            # First check for two parameter, i.e. with space after the flag
            if flag == self._module_folder_flag:
                if i + 1 == len(flags):
                    # We have a flag, but no path. Issue a warning:
                    self.logger.warning(f"Flags '{' '. join(flags)} contain "
                                        f"module path "
                                        f"'{self._module_folder_flag}' but "
                                        f"no path.")
                    break
                # Delete the two arguments: flag and path
                del flags[i:i+2]
                continue
            if flag[:flag_len] == self._module_folder_flag:
                # No space between flag and path, remove this one argument
                del flags[i]
                continue
            i += 1

    def compile_file(self, input_file: Path, output_file: Path,
                     add_flags: List[str] = None,
                     syntax_only: bool = False):
        # Do we need to remove compile flag or module_folder_flag from
        # add_flags??
        params = [input_file.name, self._compile_flag,
                  self._output_flag, str(output_file)]
        if syntax_only and self._syntax_only_flag:
            params.append(self._syntax_only_flag)
        if add_flags:
            # Don't modify the user's list:
            new_flags = add_flags[:]
            self._remove_managed_flags(new_flags)
            params += new_flags

        # Append module output path
        if self._module_folder_flag:
            params.append(self._module_folder_flag)
            params.append(self._module_output_path)

        return self.run(cwd=input_file.parent,
                        additional_parameters=params)

    def get_version(self):
        """
        Try to get the version of the given compiler.

        Expects a version in a certain part of the --version output,
        which must adhere to the n.n.n format, with at least 2 parts.

        Returns a version string, e.g '6.10.1', or empty string.
        """
        if self._version:
            return self._version

        try:
            res = self.run("--version", capture_output=True)
        except FileNotFoundError as err:
            raise ValueError(f'Compiler not found: {self.name}') from err
        except RuntimeError as err:
            self.logger.warning(f"Error asking for version of compiler "
                                f"'{self.name}': {err}")
            return ''

        # Pull the version string from the command output.
        # All the versions of gfortran and ifort we've tried follow the
        # same pattern, it's after a ")".
        try:
            version = res.split(')')[1].split()[0]
        except IndexError:
            self.logger.warning(f"Unexpected version response from "
                                f"compiler '{self.name}': {res}")
            return ''

        # expect major.minor[.patch, ...]
        # validate - this may be overkill
        split = version.split('.')
        if len(split) < 2:
            self.logger.warning(f"unhandled compiler version format for "
                                f"compiler '{self.name}' is not "
                                f"<n.n[.n, ...]>: {version}")
            return ''

        # todo: do we care if the parts are integers? Not all will be,
        # but perhaps major and minor?

        self.logger.info(f'Found compiler version for {self.name} = {version}')
        self._version = version
        return version


# ============================================================================
class Gcc(Compiler):
    '''Class for GNU's gcc compiler.
    '''
    def __init__(self):
        super().__init__("gcc", "gcc", Categories.C_COMPILER)


# ============================================================================
class Gfortran(Compiler):
    '''Class for GNU's gfortran compiler.
    '''
    def __init__(self):
        super().__init__("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                         module_folder_flag="-J",
                         omp_flag="-fopenmp",
                         syntax_only_flag="-fsyntax-only")


# ============================================================================
class Icc(Compiler):
    '''Class for the Intel's icc compiler.
    '''
    def __init__(self):
        super().__init__("icc", "icc", Categories.C_COMPILER)


# ============================================================================
class Ifort(Compiler):
    '''Class for Intel's ifort compiler.
    '''
    def __init__(self):
        super().__init__("ifort", "ifort", Categories.FORTRAN_COMPILER,
                         module_folder_flag="-module",
                         omp_flag="-qopenmp",
                         syntax_only_flag="-syntax-only")

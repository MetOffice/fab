##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and two derived
classes for gfortran and ifort

"""

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Compiler(Tool):
    '''This is the base class for any compiler.
    '''

    def __init__(self, name: str, exec_name: str, category: Categories):
        super().__init__(name, exec_name, category)
        self._version = None

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
        super().__init__("gfortran", "gfortran", Categories.FORTRAN_COMPILER)


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
        super().__init__("ifort", "ifort", Categories.FORTRAN_COMPILER)

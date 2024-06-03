##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and derived
classes for gcc, gfortran, icc, ifort
"""

import os
from pathlib import Path
from typing import List, Optional, Union
import zlib

from fab.tools.categories import Categories
from fab.tools.flags import Flags
from fab.tools.tool import VendorTool


class Compiler(VendorTool):
    '''This is the base class for any compiler. It provides flags for

    - compilation only (-c),
    - naming the output file (-o),
    - OpenMP

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param vendor: name of the compiler vendor.
    :param category: the Category (C_COMPILER or FORTRAN_COMPILER).
    :param compile_flag: the compilation flag to use when only requesting
        compilation (not linking).
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param omp_flag: the flag to use to enable OpenMP
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, vendor: str,
                 category: Categories,
                 compile_flag: Optional[str] = None,
                 output_flag: Optional[str] = None,
                 omp_flag: Optional[str] = None):
        super().__init__(name, exec_name, vendor, category)
        self._version = None
        self._compile_flag = compile_flag if compile_flag else "-c"
        self._output_flag = output_flag if output_flag else "-o"
        self._omp_flag = omp_flag
        self.flags.extend(os.getenv("FFLAGS", "").split())

    def get_hash(self) -> int:
        ''':returns: a hash based on the compiler name and version.
        '''
        return (zlib.crc32(self.name.encode()) +
                zlib.crc32(str(self.get_version()).encode()))

    def compile_file(self, input_file: Path, output_file: Path,
                     add_flags: Union[None, List[str]] = None):
        '''Compiles a file. It will add the flag for compilation-only
        automatically, as well as the output directives. The current working
        directory for the command is set to the folder where the source file
        lives when compile_file is called. This is done to stop the compiler
        inserting folder information into the mod files, which would cause
        them to have different checksums depending on where they live.

        :param input_file: the path of the input file.
        :param outpout_file: the path of the output file.
        :param add_flags: additional compiler flags.
        '''

        params: List[Union[Path, str]] = [self._compile_flag]
        if add_flags:
            params += add_flags

        params.extend([input_file.name,
                      self._output_flag, str(output_file)])

        return self.run(cwd=input_file.parent,
                        additional_parameters=params)

    def check_available(self) -> bool:
        '''
        :returns: whether the compiler is available or not. We do
            this by requesting the compiler version.
        '''
        try:
            version = self.get_version()
        except RuntimeError:
            # Compiler does not exist:
            return False

        # An empty string is returned if some other error occurred when trying
        # to get the compiler version.
        return version != ""

    def get_version(self):
        """
        Try to get the version of the given compiler.
        # TODO: why return "" when an error happened?
        # TODO: we need to properly create integers for compiler versions
        #       to (later) allow less and greater than comparisons.

        Expects a version in a certain part of the --version output,
        which must adhere to the n.n.n format, with at least 2 parts.

        :Returns: a version string, e.g '6.10.1', or empty string if
            a different error happened when trying to get the compiler version.

        :raises RuntimeError: if the compiler was not found.
        """
        if self._version:
            return self._version

        try:
            res = self.run("--version", capture_output=True)
        except FileNotFoundError as err:
            raise RuntimeError(f'Compiler not found: {self.name}') from err
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
class CCompiler(Compiler):
    '''This is the base class for a C compiler. It just sets the category
    of the compiler as convenience.

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param vendor: name of the compiler vendor.
    :param category: the Category (C_COMPILER or FORTRAN_COMPILER).
    :param compile_flag: the compilation flag to use when only requesting
        compilation (not linking).
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param omp_flag: the flag to use to enable OpenMP
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, vendor: str,
                 compile_flag=None, output_flag=None, omp_flag=None):
        super().__init__(name, exec_name, vendor, Categories.C_COMPILER,
                         compile_flag, output_flag, omp_flag)


# ============================================================================
class FortranCompiler(Compiler):
    '''This is the base class for a Fortran compiler. It is a compiler
    that needs to support a module output path and support for syntax-only
    compilation (which will only generate the .mod files).

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param vendor: name of the compiler vendor.
    :param module_folder_flag: the compiler flag to indicate where to
        store created module files.
    :param syntax_only_flag: flag to indicate to only do a syntax check.
        The side effect is that the module files are created.
    :param compile_flag: the compilation flag to use when only requesting
        compilation (not linking).
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param omp_flag: the flag to use to enable OpenMP
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, vendor: str,
                 module_folder_flag: str, syntax_only_flag=None,
                 compile_flag=None, output_flag=None, omp_flag=None):

        super().__init__(name, exec_name, vendor, Categories.FORTRAN_COMPILER,
                         compile_flag, output_flag, omp_flag)
        self._module_folder_flag = module_folder_flag
        self._module_output_path = ""
        self._syntax_only_flag = syntax_only_flag

    @property
    def has_syntax_only(self) -> bool:
        ''':returns: whether this compiler supports a syntax-only feature.'''
        return self._syntax_only_flag is not None

    def set_module_output_path(self, path: Path):
        '''Sets the output path for modules.

        :params path: the path to the output directory.
        '''
        self._module_output_path = str(path)

    def compile_file(self, input_file: Path, output_file: Path,
                     add_flags: Union[None, List[str]] = None,
                     syntax_only: bool = False):
        '''Compiles a file.

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check
        '''

        params: List[str] = []
        if add_flags:
            new_flags = Flags(add_flags)
            new_flags.remove_flag(self._module_folder_flag, has_parameter=True)
            new_flags.remove_flag(self._compile_flag, has_parameter=False)
            params += new_flags

        if syntax_only and self._syntax_only_flag:
            params.append(self._syntax_only_flag)

        # Append module output path
        if self._module_folder_flag and self._module_output_path:
            params.append(self._module_folder_flag)
            params.append(self._module_output_path)
        super().compile_file(input_file, output_file, params)


# ============================================================================
class Gcc(CCompiler):
    '''Class for GNU's gcc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "gcc",
                 exec_name: str = "gcc"):
        super().__init__(name, exec_name, "gnu", omp_flag="-fopenmp")


# ============================================================================
class Gfortran(FortranCompiler):
    '''Class for GNU's gfortran compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "gfortran",
                 exec_name: str = "gfortran"):
        super().__init__(name, exec_name, "gnu",
                         module_folder_flag="-J",
                         omp_flag="-fopenmp",
                         syntax_only_flag="-fsyntax-only")


# ============================================================================
class Icc(CCompiler):
    '''Class for the Intel's icc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "icc",
                 exec_name: str = "icc"):
        super().__init__(name, exec_name, "intel", omp_flag="-qopenmp")


# ============================================================================
class Ifort(FortranCompiler):
    '''Class for Intel's ifort compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "ifort",
                 exec_name: str = "ifort"):
        super().__init__(name, exec_name, "intel",
                         module_folder_flag="-module",
                         omp_flag="-qopenmp",
                         syntax_only_flag="-syntax-only")

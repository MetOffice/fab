##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and derived
classes for gcc, gfortran, icc, ifort
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union
import zlib

from fab.tools.category import Category
from fab.tools.flags import Flags
from fab.tools.tool import CompilerSuiteTool


class Compiler(CompilerSuiteTool):
    '''This is the base class for any compiler. It provides flags for

    - compilation only (-c),
    - naming the output file (-o),
    - OpenMP

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite this tool belongs to.
    :param category: the Category (C_COMPILER or FORTRAN_COMPILER).
    :param compile_flag: the compilation flag to use when only requesting
        compilation (not linking).
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param omp_flag: the flag to use to enable OpenMP
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str,
                 exec_name: Union[str, Path],
                 suite: str,
                 category: Category,
                 compile_flag: Optional[str] = None,
                 output_flag: Optional[str] = None,
                 omp_flag: Optional[str] = None):
        super().__init__(name, exec_name, suite, category)
        self._version: Union[Tuple[int, ...], None] = None
        self._compile_flag = compile_flag if compile_flag else "-c"
        self._output_flag = output_flag if output_flag else "-o"
        self._omp_flag = omp_flag
        self.flags.extend(os.getenv("FFLAGS", "").split())

    def get_hash(self) -> int:
        ''':returns: a hash based on the compiler name and version.
        '''
        return (zlib.crc32(self.name.encode()) +
                zlib.crc32(self.get_version_string().encode()))

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
        '''Checks if the compiler is available. While the method in
        the Tools base class would be sufficient (when using --version),
        in case of a compiler we also want to store the compiler version.
        So, re-implement check_available in a way that will automatically
        store the compiler version for later usage.

        :returns: whether the compiler is available or not. We do
            this by requesting the compiler version.
        '''
        try:
            self.get_version()
            # A valid version means the compiler is available.
            return True
        except RuntimeError as err:
            # Compiler does not exist, or version could not be handled:
            self.logger.error(f'Error getting compiler version: {err}')
            return False

    def get_version(self) -> Tuple[int, ...]:
        """
        Try to get the version of the given compiler.

        Expects a version in a certain part of the --version output,
        which must adhere to the n.n.n format, with at least 2 parts.

        :returns: a tuple of at least 2 integers, representing the version
            e.g. (6, 10, 1) for version '6.10.1'.

        :raises RuntimeError: if the compiler was not found, or if it returned
            an unrecognised output from the version command.
        """
        if self._version is not None:
            return self._version

        # Run the compiler to get the version and parse the output
        # The implementations depend on vendor
        output = self.run_version_command()
        version_string = self._parse_version_output(output)

        # Expect the version to be dot-separated integers.
        # todo: Not all will be integers? but perhaps major and minor?
        try:
            version = tuple(int(x) for x in version_string.split('.'))
        except ValueError as err:
            raise RuntimeError(f"Unexpected version output format for "
                               f"compiler '{self.name}'. Should be numeric "
                               f"<n.n[.n, ...]>: {version_string}") from err

        # Expect at least 2 integer components, i.e. major.minor[.patch, ...]
        if len(version) < 2:
            raise RuntimeError(f"Unexpected version output format for "
                               f"compiler '{self.name}'. Should have at least "
                               f"two parts, <n.n[.n, ...]>: {version_string}")

        self.logger.info(
            f'Found compiler version for {self.name} = {version_string}')
        self._version = version
        return version

    def run_version_command(
            self, version_command: Optional[str] = '--version') -> str:
        '''
        Run the compiler's command to get its version.

        :param version_command: The compiler argument used to get version info.

        :returns: The output from the version command.

        :raises RuntimeError: if the compiler was not found, or raised an error.
        '''
        try:
            return self.run(version_command, capture_output=True)
        except RuntimeError as err:
            raise RuntimeError(f"Error asking for version of compiler "
                               f"'{self.name}'") from err

    def _parse_version_output(self, version_output) -> str:
        '''
        Extract the numerical part from the version output.
        Implemented in subclasses for specific compilers.
        '''
        raise NotImplementedError

    def get_version_string(self) -> str:
        """
        Get a string representing the version of the given compiler.

        :returns: a string of at least 2 numeric version components,
            i.e. major.minor[.patch, ...]

        :raises RuntimeError: if the compiler was not found, or if it returned
            an unrecognised output from the version command.
        """
        version = self.get_version()
        return '.'.join(str(x) for x in version)


# ============================================================================
class CCompiler(Compiler):
    '''This is the base class for a C compiler. It just sets the category
    of the compiler as convenience.

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite.
    :param compile_flag: the compilation flag to use when only requesting
        compilation (not linking).
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param omp_flag: the flag to use to enable OpenMP
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, suite: str, compile_flag=None,
                 output_flag=None, omp_flag=None):
        super().__init__(name, exec_name, suite, Category.C_COMPILER,
                         compile_flag, output_flag, omp_flag)


# ============================================================================
class FortranCompiler(Compiler):
    '''This is the base class for a Fortran compiler. It is a compiler
    that needs to support a module output path and support for syntax-only
    compilation (which will only generate the .mod files).

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite.
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
    def __init__(self, name: str, exec_name: str, suite: str,
                 module_folder_flag: str, syntax_only_flag=None,
                 compile_flag=None, output_flag=None, omp_flag=None):

        super().__init__(name, exec_name, suite, Category.FORTRAN_COMPILER,
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
class GnuVersionHandling(Compiler):
    '''Mixin to handle version information from GNU compilers'''

    def _parse_version_output(self, version_output: str) -> str:
        '''
        Extract the numerical part from the version output

        :param version_output: the full version output from the compiler
        :returns: the actual version as a string

        :raises RuntimeError: if the output is not in an expected format.
        '''

        # Expect the version to appear after some in parentheses, e.g.
        # "GNU Fortran (...) n.n[.n, ...]" or # "gcc (...) n.n[.n, ...]"
        display_name = self.name
        if self.category is Category.FORTRAN_COMPILER:
            display_name = 'GNU Fortran'

        exp = display_name + r" \(.*?\) (\d[\d\.]+\d)\b"
        matches = re.findall(exp, version_output)
        if not matches:
            raise RuntimeError(f"Unexpected version output format for compiler "
                               f"'{self.name}': {version_output}")
        return matches[0]


# ============================================================================
class Gcc(GnuVersionHandling, CCompiler):
    '''Class for GNU's gcc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "gcc",
                 exec_name: str = "gcc"):
        super().__init__(name, exec_name, "gnu", omp_flag="-fopenmp")


# ============================================================================
class Gfortran(GnuVersionHandling, FortranCompiler):
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
class IntelVersionHandling(Compiler):
    '''Mixin to handle version information from Intel compilers'''

    def _parse_version_output(self, version_output: str) -> str:
        '''
        Extract the numerical part from the version output

        :param version_output: the full version output from the compiler
        :returns: the actual version as a string

        :raises RuntimeError: if the output is not in an expected format.
        '''

        # Expect the version to appear after some in parentheses, e.g.
        # "icc (...) n.n[.n, ...]" or "ifort (...) n.n[.n, ...]"
        exp = self.name + r" \(.*?\) (\d[\d\.]+\d)\b"
        matches = re.findall(exp, version_output)

        if not matches:
            raise RuntimeError(f"Unexpected version output format for compiler "
                               f"'{self.name}': {version_output}")
        return matches[0]


# ============================================================================
class Icc(IntelVersionHandling, CCompiler):
    '''Class for the Intel's icc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "icc",
                 exec_name: str = "icc"):
        super().__init__(name, exec_name, "intel-classic",
                         omp_flag="-qopenmp")


# ============================================================================
class Ifort(IntelVersionHandling, FortranCompiler):
    '''Class for Intel's ifort compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self,
                 name: str = "ifort",
                 exec_name: str = "ifort"):
        super().__init__(name, exec_name, "intel-classic",
                         module_folder_flag="-module",
                         omp_flag="-qopenmp",
                         syntax_only_flag="-syntax-only")

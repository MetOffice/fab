##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and derived
classes for gcc, gfortran, icc, ifort
"""

import re
from pathlib import Path
import warnings
from typing import cast, Optional, Union

from fab.build_config import BuildConfig
from fab.tools.category import Category
from fab.tools.flags import AlwaysFlags
from fab.tools.compiler_suite_tool import CompilerSuiteTool
from fab.util import string_checksum


class Compiler(CompilerSuiteTool):
    '''This is the base class for any compiler. It provides generic flags
    for common settings, which must be defined by the compiler-specific
    derived classes.

    The following generic flags are used within Fab itself, and so must be
    provided by all compiler instances:

    - compilation-only (e.g. -c)
    - output (e.g. -o)
    - include-path (e.g. -I)
    - openmp (e.g. -fopenmp, or -qopenmp, ..)
    - module-search-path (for Fortran compilers, e.g. -I)
    - module-out-folder (for Fortran compiler, e.g. -J)

    The following generic flags are also defined for any compilers
    in Fab, but they are not used by Fab itself, but might be very
    convenient for application scripts

    - default-8-byte-real      (for Fortran compiler)
    - default-8-byte-double    (for Fortran compiler, required if the compiler
                                change default double precision to 64 bit if
                                default-8-byte-real is selected)
    - default-8-byte-integer   (for Fortran compiler)

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite this tool belongs to.
    :param version_regex: A regular expression that allows extraction of
        the version number from the version output of the compiler. The
        version is taken from the first group of a match.
    :param category: the Category (C_COMPILER or FORTRAN_COMPILER).
    :param mpi: whether the compiler or linker support MPI.
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    :param availability_option: a command line option for the tool to test
        if the tool is available on the current system. Defaults to
        `--version`.
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str,
                 exec_name: Union[str, Path],
                 suite: str,
                 version_regex: str,
                 category: Category,
                 mpi: bool = False,
                 version_argument: Optional[str] = None,
                 availability_option: Optional[Union[str, list[str]]] = None):
        super().__init__(name, exec_name, suite, category=category,
                         availability_option=availability_option)
        self._version: Union[tuple[int, ...], None] = None
        self._mpi = mpi
        self.__version_argument = version_argument or '--version'
        self._version_regex = version_regex

        # Setup generic flags. We define some flags here in the base class
        # since they are pretty much standardised across all compilers,
        # but any compiler can overwrite these options.
        self["compile-only"] = "-c"
        self["output"] = "-o"
        self["include-path"] = "-I"

    @property
    def mpi(self) -> bool:
        """
        :returns: whether this compiler supports MPI or not.
        """
        return self._mpi

    @property
    def openmp(self) -> bool:
        """
        :returns: compiler's OpenMP support.
        """
        # It is important not to use `_openmp_flag` directly, since a compiler
        # wrapper overwrites `openmp_flag`.
        try:
            return self["openmp"] != []
        except KeyError:
            return False

    def get_hash(self,
                 config: "BuildConfig",
                 file_path: Path
                 ) -> int:
        """
        Computes a hash code using the name and version of the compiler,
        and the compilation flag used by the compiler for the specified
        file.

        :param config: The build configuration to use.
        :param file_path: Path of the file to compile.
        :returns: hash of compiler name and version.
        """
        all_params = (self.name +
                      self.get_version_string() +
                      str(self.get_flags(config, file_path)))
        return string_checksum(all_params)

    def get_all_commandline_options(
            self,
            config: "BuildConfig",
            input_file: Path,
            output_file: Path,
            add_flags:  Union[None, list[str]] = None) -> list[str]:
        '''This function returns all command line options for a compiler
        (but not the executable name). It is used by a compiler wrapper
        to pass the right flags to the wrapper.
        This base implementation adds the input and output filename (including
        the -o flag), the flag to only compile (and not link), and if
        required openmp.

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional flags for the compiler.

        :returns: all command line options for compilation.
        '''
        # Make a copy so we do not modify the original files.
        params: list[str] = self["compile-only"][:]

        if config.openmp:
            params.extend(self["openmp"])

        # Explicitly add all compilation flags here, where the input
        # path can be provided to properly resolve path-specific flags.
        params += self.get_flags(config, input_file)

        if add_flags:
            if self["openmp"][0] in add_flags:
                warnings.warn(
                    f"OpenMP flag '{self['openmp']}' explicitly provided. "
                    f"OpenMP should be enabled in the BuildConfiguration "
                    f"instead.")
            params += add_flags

        params.append(input_file.name)
        params.extend(self["output"])
        params.append(str(output_file))
        return params

    def get_flags(self, config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        The flags to use when compiling the specified flag. All
        AbstractFlags (e.g. MatchFlags, ...) will be resolved.

        :param config: The build configuration to use.
        :param file_path: the path to the file to be compiled.

        :returns: the flags actually used when building the specified
            path.
        """
        return self.flags.get_flags(config, file_path)

    def compile_file(self, input_file: Path,
                     output_file: Path,
                     config: "BuildConfig",
                     add_flags: Union[None, list[str]] = None):
        '''Compiles a file. It will add the flag for compilation-only
        automatically, as well as the output directives. The current working
        directory for the command is set to the folder where the source file
        lives when compile_file is called. This is done to stop the compiler
        inserting folder information into the mod files, which would cause
        them to have different checksums depending on where they live.

        :param input_file: the path of the input file.
        :param output_file: the path of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional compiler flags.
        '''

        params = self.get_all_commandline_options(config, input_file,
                                                  output_file, add_flags)
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

    def get_version(self) -> tuple[int, ...]:
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
        output = self.run_version_command(self.__version_argument)

        # Multiline is required in case that the version number is the end
        # of the string, otherwise the $ would not match the end of line
        matches = re.search(self._version_regex, output, re.MULTILINE)
        if not matches:
            raise RuntimeError(f"Unexpected version output format for "
                               f"compiler '{self.name}': {output}")
        version_string = matches.groups()[0]
        # Expect the version to be dot-separated integers.
        try:
            # Make mypy happy:
            version = cast(tuple[int],
                           tuple(int(x) for x in version_string.split('.')))
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

        :raises RuntimeError: if the compiler was not found, or raised an
            error.
        '''
        try:
            return self.run(version_command, capture_output=True)
        except RuntimeError as err:
            raise RuntimeError(f"Error asking for version of compiler "
                               f"'{self.name}'") from err

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
    :param version_regex: A regular expression that allows extraction of
        the version number from the version output of the compiler.
    :param mpi: whether the compiler or linker support MPI.
    :param output_flag: the compilation flag to use to indicate the name
        of the output file
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, suite: str,
                 version_regex: str,
                 mpi: bool = False,
                 version_argument: Optional[str] = None,
                 availability_option: Optional[str] = None):
        super().__init__(name, exec_name, suite,
                         category=Category.C_COMPILER, mpi=mpi,
                         version_argument=version_argument,
                         version_regex=version_regex,
                         availability_option=availability_option)


# ============================================================================
class FortranCompiler(Compiler):
    '''This is the base class for a Fortran compiler. It is a compiler
    that needs to support a module output path and support for syntax-only
    compilation (which will only generate the .mod files).

    :param name: name of the compiler.
    :param exec_name: name of the executable to start.
    :param suite: name of the compiler suite.
    :param version_regex: A regular expression that allows extraction of
        the version number from the version output of the compiler.
    :param mpi: whether MPI is supported by this compiler or not.
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, name: str, exec_name: str, suite: str,
                 version_regex: str,
                 mpi: bool = False,
                 version_argument: Optional[str] = None,
                 ):

        super().__init__(name=name, exec_name=exec_name, suite=suite,
                         category=Category.FORTRAN_COMPILER,
                         mpi=mpi,
                         version_argument=version_argument,
                         version_regex=version_regex)
        self._module_output_path = ""
        self["module-search-path"] = "-I"
        # Defining this as empty makes tests later easier
        self["module-out-folder"] = []
        self["syntax-only"] = []

    @property
    def has_syntax_only(self) -> bool:
        ''':returns: whether this compiler supports a syntax-only feature.'''
        return self["syntax-only"] != []

    def set_module_output_path(self, path: Path):
        '''Sets the output path for modules.

        :params path: the path to the output directory.
        '''
        self._module_output_path = str(path)

    def get_all_commandline_options(
            self,
            config: "BuildConfig",
            input_file: Path,
            output_file: Path,
            add_flags:  Union[None, list[str]] = None,
            syntax_only: Optional[bool] = False) -> list[str]:
        '''This function returns all command line options for a Fortran
        compiler (but not the executable name). It is used by a compiler
        wrapper to pass the right flags to the wrapper.
        This Fortran-specific implementation adds the module- and
        syntax-only flags (as required) to the standard compiler
        flags.

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check

        :returns: all command line options for Fortran compilation.
        '''
        if add_flags:
            # Create an AlwaysFlags to use its remove_flag method
            af = AlwaysFlags(add_flags)
            if self["module-out-folder"]:
                # Remove any module flag the user has specified, since
                # this will interfere with Fab's module handling.
                af.remove_flag(self["module-out-folder"][0],
                               has_parameter=True)
            af.remove_flag(self["compile-only"][0], has_parameter=False)
            add_flags = af.get_flags(config, input_file)

        # Get the flags from the base class
        params = super().get_all_commandline_options(config, input_file,
                                                     output_file, add_flags)
        if syntax_only and self["syntax-only"]:
            params.extend(self["syntax-only"])

        # Append module output path
        if self["module-out-folder"] and self._module_output_path:
            # Make sure to add the Fab module flags first, so that they
            # will overwrite what is set up otherwise. An example of this
            # is Jules, which provides its own dummy NetCDF module if
            # NetCDF is disabled. The Fab flags must come before any
            # module search path from the environment, otherwise
            # a potentially existing NetCDF module would be found.
            params[0:0] = self["module-out-folder"]
            params.insert(1, self._module_output_path)
            # It also looks like gfortran searches the module output
            # path last, independent of the order. So just in case,
            # also add an explicit include path:
            params[0:0] = self["module-search-path"]
            params.insert(1, self._module_output_path)

        return params

    def compile_file(self, input_file: Path,
                     output_file: Path,
                     config: "BuildConfig",
                     add_flags: Union[None, list[str]] = None,
                     syntax_only: Optional[bool] = False):
        '''Compiles a file. This basically re-implements `compile_file` of
        the base class, but passes the syntax_only flag in

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check
        '''
        params = self.get_all_commandline_options(config, input_file,
                                                  output_file, add_flags,
                                                  syntax_only)

        self.run(cwd=input_file.parent, additional_parameters=params)


# ============================================================================
# Gnu
# ============================================================================
class Gcc(CCompiler):
    '''Class for GNU's gcc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    :param mpi: whether the compiler supports MPI.
    '''
    def __init__(self,
                 name: str = "gcc",
                 exec_name: str = "gcc",
                 mpi: bool = False):
        # A version number is a digit, followed by a sequence of digits and
        # '.'', ending with a digit. It must then be followed by either the
        # end of the string, or a space (e.g. "... 5.6 123456"). We can't use
        # \b to determine the end, since then "1.2." would be matched
        # excluding the dot (so it would become a valid 1.2)
        super().__init__(name, exec_name, suite="gnu", mpi=mpi,
                         version_regex=r"gcc \(.*?\) (\d[\d\.]+\d)(?:$| )")
        # Setup generic flags
        self["openmp"] = "-fopenmp"


# ============================================================================
class Gfortran(FortranCompiler):
    '''Class for GNU's gfortran compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    :param mpi: whether the compiler supports MPI.
    '''

    def __init__(self, name: str = "gfortran",
                 exec_name: str = "gfortran"):
        super().__init__(name, exec_name, suite="gnu",
                         version_regex=(r"GNU Fortran \(.*?\) "
                                        r"(\d[\d\.]+\d)(?:$| )"))
        self["openmp"] = '-fopenmp'
        self["module-out-folder"] = '-J'
        self["syntax-only"] = '-fsyntax-only'
        self["default-8-byte-real"] = '-fdefault-real-8'
        # If default-real-8 is used, doubles become 16 bytes.
        self["default-8-byte-double"] = '-fdefault-double-8'
        self["default-8-byte-integer"] = '-fdefault-integer-8'


# ============================================================================
# intel-classic
# ============================================================================
class Icc(CCompiler):
    '''Class for the Intel's icc compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    :param mpi: whether the compiler supports MPI.
    '''

    def __init__(self, name: str = "icc", exec_name: str = "icc"):
        super().__init__(name, exec_name, suite="intel-classic",
                         version_regex=r"icc \(ICC\) (\d[\d\.]+\d) ")
        self["openmp"] = '-qopenmp'


# ============================================================================
class Ifort(FortranCompiler):
    '''Class for Intel's ifort compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    :param mpi: whether the compiler supports MPI.
    '''

    def __init__(self, name: str = "ifort", exec_name: str = "ifort"):
        super().__init__(name, exec_name, suite="intel-classic",
                         version_regex=r"ifort \(IFORT\) (\d[\d\.]+\d) ")
        self["openmp"] = '-qopenmp'
        self["module-out-folder"] = '-module'
        self["syntax-only"] = '-syntax-only'
        self["default-8-byte-real"] = ['-real-size', '64']
        self["default-8-byte-double"] = ['-double-size', '64']
        self["default-8-byte-integer"] = ['-integer-size', '64']


# ============================================================================
# intel-llvm
# ============================================================================
class Icx(CCompiler):
    '''Class for the Intel's new llvm based icx compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self, name: str = "icx", exec_name: str = "icx"):
        super().__init__(name, exec_name, suite="intel-llvm",
                         version_regex=(r"Intel\(R\) oneAPI DPC\+\+/C\+\+ "
                                        r"Compiler (\d[\d\.]+\d) "))
        self["openmp"] = '-qopenmp'


# ============================================================================
class Ifx(FortranCompiler):
    '''Class for Intel's new ifx compiler.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''

    def __init__(self, name: str = "ifx", exec_name: str = "ifx"):
        super().__init__(name, exec_name, suite="intel-llvm",
                         version_regex=r"ifx \(IFX\) (\d[\d\.]+\d) ")
        self["openmp"] = '-qopenmp'
        self["module-out-folder"] = '-module'
        self["syntax-only"] = '-syntax-only'
        self["default-8-byte-real"] = ['-real-size', '64']
        self["default-8-byte-double"] = ['-double-size', '64']
        self["default-8-byte-integer"] = ['-integer-size', '64']


# ============================================================================
# nvidia
# ============================================================================
class Nvc(CCompiler):
    '''Class for Nvidia's nvc compiler. Note that the '-' in the Nvidia
    version number is ignored, e.g. 23.5-0 would return '23.5'.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''

    def __init__(self, name: str = "nvc", exec_name: str = "nvc"):
        super().__init__(name, exec_name, suite="nvidia",
                         version_argument='-V',
                         version_regex=r"nvc (\d[\d\.]+\d)")
        self["openmp"] = '-mp'


# ============================================================================
class Nvfortran(FortranCompiler):
    '''Class for Nvidia's nvfortran compiler. Note that the '-' in the Nvidia
    version number is ignored, e.g. 23.5-0 would return '23.5'.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''

    def __init__(self, name: str = "nvfortran", exec_name: str = "nvfortran"):
        super().__init__(name, exec_name, suite="nvidia",
                         version_argument='-V',
                         version_regex=r"nvfortran (\d[\d\.]+\d)")
        self["openmp"] = '-mp'
        self["module-out-folder"] = '-module'
        self["syntax-only"] = '-Msyntax-only'
        self["default-8-byte-real"] = '-Mr8'
        # NvFortran doesn't have (or need) an option to enforce 8 byte
        # doubles, even if default reals are changed to double
        self["default-8-byte-double"] = []
        self["default-8-byte-integer"] = ['i8']


# ============================================================================
# Cray compiler
# ============================================================================
class Craycc(CCompiler):
    '''Class for the native Cray C compiler. Since cc is actually a compiler
    wrapper, follow the naming scheme of a compiler wrapper and call it:
    craycc-cc.

    Cray has two different compilers. Older ones have as version number:
        Cray C : Version 8.7.0  Tue Jul 23, 2024  07:39:46

    Newer compiler (several lines, the important one):
        Cray clang version 15.0.1  (66f7391d6a03cf932f321b9f6b1d8612ef5f362c)

    We use the beginning ("cray c") to identify the compiler, which works for
    both cray c and cray clang. Then we ignore non-numbers, to reach the
    version number which is then extracted.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''
    def __init__(self, name: str = "craycc-cc", exec_name: str = "cc"):
        super().__init__(name, exec_name, suite="cray", mpi=True,
                         version_regex=r"Cray [Cc][^\d]* (\d[\d\.]+\d)")
        self["openmp"] = '-homp'


# ============================================================================
class Crayftn(FortranCompiler):
    '''Class for the native Cray Fortran compiler. Since ftn is actually a
    compiler wrapper, follow the naming scheme of Cray compiler wrapper
    and call it crayftn-ftn.

    :param name: name of this compiler.
    :param exec_name: name of the executable.
    '''

    def __init__(self, name: str = "crayftn-ftn", exec_name: str = "ftn"):
        super().__init__(name, exec_name, suite="cray", mpi=True,
                         version_regex=(r"Cray Fortran : Version "
                                        r"(\d[\d\.]+\d)(\s+|$)"))
        self["openmp"] = '-omp'
        self["module-out-folder"] = '-J'
        self["syntax-only"] = '-syntax-only'
        self["default-8-byte-real"] = ['-s', 'real64']
        self["default-8-byte-double"] = []
        self["default-8-byte-integer"] = ['-s', 'integer64']

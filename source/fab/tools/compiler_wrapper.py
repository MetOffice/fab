##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler, and derived
classes for gcc, gfortran, icc, ifort
"""

from pathlib import Path
from typing import cast, List, Optional, Tuple, Union

from fab.tools.category import Category
from fab.tools.compiler import Compiler, FortranCompiler
from fab.tools.flags import Flags


class CompilerWrapper(Compiler):
    '''A decorator-based compiler wrapper. It basically uses a different
    executable name when compiling, but otherwise behaves like the wrapped
    compiler. An example of a compiler wrapper is `mpif90` (which can
    internally call e.g. gfortran, icc, ...)

    :param name: name of the wrapper.
    :param exec_name: name of the executable to call.
    :param compiler: the compiler that is decorated.
    :param mpi: whether MPI is supported by this compiler or not.
    '''

    def __init__(self, name: str, exec_name: str,
                 compiler: Compiler,
                 mpi: bool = False):
        self._compiler = compiler
        super().__init__(
            name=name, exec_name=exec_name,
            category=self._compiler.category,
            suite=self._compiler.suite,
            version_regex=self._compiler._version_regex,
            mpi=mpi,
            availability_option=self._compiler.availability_option)

    def get_version(self) -> Tuple[int, ...]:
        """Determines the version of the compiler. The implementation in the
        compiler wrapper additionally ensures that the wrapper compiler and
        compiler wrapper report both the same version. This verifies that the
        user's build environment is as expected. For example, this will check
        if mpif90 from mpif90-ifort does indeed invoke ifort (and not e.g.
        gfortran).

        :returns: a tuple of at least 2 integers, representing the version
            e.g. (6, 10, 1) for version '6.10.1'.

        :raises RuntimeError: if the compiler was not found, or if it returned
            an unrecognised output from the version command.
        :raises RuntimeError: if the compiler wrapper and wrapped compiler
            have different version numbers.
        """

        if self._version is not None:
            return self._version

        try:
            compiler_version = self._compiler.get_version()
        except RuntimeError as err:
            raise RuntimeError(f"Cannot get version of wrapped compiler '"
                               f"{self._compiler}") from err

        wrapper_version = super().get_version()
        if compiler_version != wrapper_version:
            compiler_version_string = self._compiler.get_version_string()
            # We cannot call super().get_version_string(), since this calls
            # calls get_version(), so we get an infinite recursion
            wrapper_version_string = ".".join(str(x) for x in wrapper_version)
            raise RuntimeError(f"Different version for compiler "
                               f"'{self._compiler}' "
                               f"({compiler_version_string}) and compiler "
                               f"wrapper '{self}' ({wrapper_version_string}).")
        self._version = wrapper_version
        return wrapper_version

    @property
    def compiler(self) -> Compiler:
        ''':returns: the compiler that is wrapped by this CompilerWrapper.'''
        return self._compiler

    @property
    def flags(self) -> Flags:
        ''':returns: the flags to be used with this tool.'''
        return Flags(self._compiler.flags + self._flags)

    @property
    def suite(self) -> str:
        ''':returns: the compiler suite of this tool.'''
        return self._compiler.suite

    @property
    def openmp_flag(self) -> str:
        '''Returns the flag to enable OpenMP.'''
        return self._compiler.openmp_flag

    @property
    def has_syntax_only(self) -> bool:
        ''':returns: whether this compiler supports a syntax-only feature.

        :raises RuntimeError: if this function is called for a non-Fortran
            wrapped compiler.
        '''

        if self._compiler.category == Category.FORTRAN_COMPILER:
            return cast(FortranCompiler, self._compiler).has_syntax_only

        raise RuntimeError(f"Compiler '{self._compiler.name}' has "
                           f"no has_syntax_only.")

    def set_module_output_path(self, path: Path):
        '''Sets the output path for modules.

        :params path: the path to the output directory.

        :raises RuntimeError: if this function is called for a non-Fortran
            wrapped compiler.
        '''

        if self._compiler.category != Category.FORTRAN_COMPILER:
            raise RuntimeError(f"Compiler '{self._compiler.name}' has no "
                               f"'set_module_output_path' function.")
        cast(FortranCompiler, self._compiler).set_module_output_path(path)

    def compile_file(self, input_file: Path,
                     output_file: Path,
                     openmp: bool,
                     add_flags: Union[None, List[str]] = None,
                     syntax_only: Optional[bool] = None):
        # pylint: disable=too-many-arguments
        '''Compiles a file using the wrapper compiler. It will temporarily
        change the executable name of the wrapped compiler, and then calls
        the original compiler (to get all its parameters)

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param openmp: if compilation should be done with OpenMP.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check
        '''

        # TODO #370: replace change_exec_name, and instead provide
        # a function that returns the whole command line, which can
        # then be modified here.
        orig_compiler_name = self._compiler.exec_name
        self._compiler.change_exec_name(self.exec_name)
        if add_flags is None:
            add_flags = []
        if self._compiler.category is Category.FORTRAN_COMPILER:
            # Mypy complains that self._compiler does not take the syntax
            # only parameter. Since we know it's a FortranCompiler.
            # do a cast to tell mypy that this is now a Fortran compiler
            # (or a CompilerWrapper in case of nested CompilerWrappers,
            # which also supports the syntax_only flag anyway)
            self._compiler = cast(FortranCompiler, self._compiler)
            self._compiler.compile_file(input_file, output_file, openmp=openmp,
                                        add_flags=self.flags + add_flags,
                                        syntax_only=syntax_only,
                                        )
        else:
            if syntax_only is not None:
                raise RuntimeError(f"Syntax-only cannot be used with compiler "
                                   f"'{self.name}'.")
            self._compiler.compile_file(input_file, output_file, openmp=openmp,
                                        add_flags=self.flags+add_flags
                                        )
        self._compiler.change_exec_name(orig_compiler_name)


# ============================================================================
class Mpif90(CompilerWrapper):
    '''Class for a simple wrapper for using a compiler driver (like mpif90)
    It will be using the name "mpif90-COMPILER_NAME" and calls `mpif90`.
    All flags from the original compiler will be used when using the wrapper
    as compiler.

    :param compiler: the compiler that the mpif90 wrapper will use.
    '''

    def __init__(self, compiler: Compiler):
        super().__init__(name=f"mpif90-{compiler.name}",
                         exec_name="mpif90", compiler=compiler, mpi=True)


# ============================================================================
class Mpicc(CompilerWrapper):
    '''Class for a simple wrapper for using a compiler driver (like mpicc)
    It will be using the name "mpicc-COMPILER_NAME" and calls `mpicc`.
    All flags from the original compiler will be used when using the wrapper
    as compiler.

    :param compiler: the compiler that the mpicc wrapper will use.
    '''

    def __init__(self, compiler: Compiler):
        super().__init__(name=f"mpicc-{compiler.name}",
                         exec_name="mpicc", compiler=compiler, mpi=True)


# ============================================================================
class CrayFtnWrapper(CompilerWrapper):
    '''Class for the Cray Fortran compiler wrapper. We add 'wrapper' to the
    class name to make this class distinct from the Crayftn compiler class.

    :param compiler: the compiler that the ftn wrapper will use.
    '''

    def __init__(self, compiler: Compiler):
        super().__init__(name=f"crayftn-{compiler.name}",
                         exec_name="ftn", compiler=compiler, mpi=True)


# ============================================================================
class CrayCcWrapper(CompilerWrapper):
    '''Class for the Cray C compiler wrapper. We add 'wrapper' to the class
    name to make this class distinct from the Craycc compiler class

    :param compiler: the compiler that the mpicc wrapper will use.
    '''

    def __init__(self, compiler: Compiler):
        super().__init__(name=f"craycc-{compiler.name}",
                         exec_name="cc", compiler=compiler, mpi=True)

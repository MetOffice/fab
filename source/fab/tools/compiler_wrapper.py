##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any compiler-wrapper, including
the derived classes for mpif90, mpicc, and CrayFtnWrapper and CrayCcWrapper.
"""

from pathlib import Path
from typing import cast, List, Optional, TYPE_CHECKING, Union

from fab.tools.category import Category
from fab.tools.compiler import Compiler, FortranCompiler
from fab.tools.flags import Flags
if TYPE_CHECKING:
    from fab.build_config import BuildConfig


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

    @property
    def compiler(self) -> Compiler:
        ''':returns: the compiler that is wrapped by this CompilerWrapper.'''
        return self._compiler

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

    def get_flags(self, profile: Optional[str] = None) -> List[str]:
        ''':returns: the ProfileFlags for the given profile, combined
            from the wrapped compiler and this wrapper.

        :param profile: the profile to use.
        '''
        return (self._compiler.get_flags(profile) +
                super().get_flags(profile))

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

    def get_all_commandline_options(
            self,
            config: "BuildConfig",
            input_file: Path,
            output_file: Path,
            add_flags:  Union[None, List[str]] = None,
            syntax_only: Optional[bool] = False) -> List[str]:
        '''This function returns all command line options for a
        compiler wrapper. The syntax_only flag is only accepted,
        if the wrapped compiler is a Fortran compiler. Otherwise,
        an exception will be raised.

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check

        :returns: command line flags for compiler wrapper.

        :raises RuntimeError: if syntax_only is requested for a non-Fortran
            compiler.
        '''
        # We need to distinguish between Fortran and non-Fortran compiler,
        # since only a Fortran compiler supports the syntax-only flag.
        new_flags = Flags(add_flags)

        if self._compiler.category is Category.FORTRAN_COMPILER:
            # Mypy complains that self._compiler does not take the syntax
            # only parameter. Since we know it's a FortranCompiler.
            # do a cast to tell mypy that this is now a Fortran compiler
            # (or a CompilerWrapper in case of nested CompilerWrappers,
            # which also supports the syntax_only flag anyway).
            self._compiler = cast(FortranCompiler, self._compiler)
            if self._compiler._module_folder_flag:
                # Remove a user's module flag, which would interfere
                # with Fab's module handling.
                new_flags.remove_flag(self._compiler._module_folder_flag,
                                      has_parameter=True)
            flags = self._compiler.get_all_commandline_options(
                    config, input_file, output_file, add_flags=add_flags,
                    syntax_only=syntax_only)
        else:
            # It's not valid to specify syntax_only for a non-Fortran compiler
            if syntax_only is not None:
                raise RuntimeError(f"Syntax-only cannot be used with compiler "
                                   f"'{self.name}'.")
            flags = self._compiler.get_all_commandline_options(
                    config, input_file, output_file, add_flags=add_flags)

        return flags

    def compile_file(self, input_file: Path,
                     output_file: Path,
                     config: "BuildConfig",
                     add_flags: Union[None, List[str]] = None,
                     syntax_only: Optional[bool] = None):
        # pylint: disable=too-many-arguments
        '''Compiles a file using the wrapper compiler.

        :param input_file: the name of the input file.
        :param output_file: the name of the output file.
        :param config: The BuildConfig, from which compiler profile and OpenMP
            status are taken.
        :param add_flags: additional flags for the compiler.
        :param syntax_only: if set, the compiler will only do
            a syntax check
        '''

        flags = self.get_all_commandline_options(
            config, input_file, output_file, add_flags=add_flags,
            syntax_only=syntax_only)

        self.run(profile=config.profile, cwd=input_file.parent,
                 additional_parameters=flags)


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

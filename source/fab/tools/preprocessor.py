##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for any preprocessor, and two derived
classes for cpp and fpp.

"""

from pathlib import Path
from typing import List, Union

from fab.tools.categories import Categories
from fab.tools.tool import Tool


class Preprocessor(Tool):
    '''This is the base class for any preprocessor.

    :param name: the name of the preprocessor.
    :param exec_name: the name of the executable.
    :param category: the category (C_PREPROCESSOR or FORTRAN_PREPROCESSOR)
    '''

    def __init__(self, name: str, exec_name: str, category: Categories):
        super().__init__(name, exec_name, category)
        self._version = None

    def check_available(self) -> bool:
        '''
        :returns: whether the preprocessor is available or not. We do
            this by requesting the compiler version.
        '''
        try:
            self.run("--version")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

    def preprocess(self, input_file: Path, output_file: Path,
                   add_flags: Union[None, List[Union[Path, str]]] = None):
        '''Calls the preprocessor to process the specified input file,
        creating the requested output file.

        :param input_file: input file.
        :param output_file: the output filename.
        :param add_flags: List with additional flags to be used.
        '''
        params: List[Union[str, Path]] = []
        if add_flags:
            # Make a copy to avoid modifying the caller's list
            params = add_flags[:]
        # Input and output files come as the last two parameters
        params.extend([input_file, output_file])

        return self.run(additional_parameters=params)


# ============================================================================
class Cpp(Preprocessor):
    '''Class for cpp.
    '''
    def __init__(self):
        super().__init__("cpp", "cpp", Categories.C_PREPROCESSOR)


# ============================================================================
class CppFortran(Preprocessor):
    '''Class for cpp when used as a Fortran preprocessor
    '''
    def __init__(self):
        super().__init__("cpp", "cpp", Categories.FORTRAN_PREPROCESSOR)
        self.flags.extend(["-traditional-cpp", "-P"])


# ============================================================================
class Fpp(Preprocessor):
    '''Class for Intel's Fortran-specific preprocessor.
    '''
    def __init__(self):
        super().__init__("fpp", "fpp", Categories.FORTRAN_PREPROCESSOR)

    def check_available(self):
        '''Checks if the compiler is available. We do this by requesting the
        compiler version.
        '''
        try:
            # fpp -V prints version information, but then hangs (i.e. reading
            # from stdin), so use -what
            self.run("-what")
        except (RuntimeError, FileNotFoundError):
            return False
        return True

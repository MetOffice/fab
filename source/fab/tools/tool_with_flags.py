##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for a tool with flags.
It is the base class for compiler, linker, and pre-processor.

"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING, Union

from fab.tools.category import Category
from fab.tools.flags import AbstractFlags, ProfileFlags
from fab.tools.tool import Tool

if TYPE_CHECKING:
    from fab.build_config import BuildConfig


class ToolWithFlags(Tool):
    '''This is the base class for all tools that provide flags.
    Note that the `run` method of the Tool base class is not overwritten
    to provide the flags to the base class, that needs to be done
    by the individual derived tools.

    This tool also implements support for generic flags, i.e. (say)
    compiler-specific flags that can be accessed using a common name.
    For example, `compiler["include"]` might be `-I`, and
    `compiler["module-output-path"]` = `-J` (for Gnu) or `-module`
    (for Intel).

    :param name: name of the tool.
    :param exec_name: name or full path of the executable to start.
    :param category: the Category to which this tool belongs.
    :param availability_option: a command line option for the tool to test
        if the tool is available on the current system. Defaults to
        `--version`.
    '''

    def __init__(
            self,
            name: str,
            exec_name: Union[str, Path],
            category: Category,
            availability_option: Optional[Union[str,
                                                list[str]]] = None) -> None:

        super().__init__(name, exec_name, category, availability_option)
        self._flags = ProfileFlags()
        # Note that the value is always a list of flags. That is convenient
        # in case that a compiler needs more than one flag (e.g. to enable
        # 8-byte-default real, which might need settings for real and double).
        # Standard flags are implicitly assumed to be a single flag (e.g.
        # -c, -o).
        self._generic_flags: dict[str, list[str]] = {}

    def __getitem__(self, generic_name: str) -> list[str]:
        """
        Returns the compiler-specific list of flags given a generic
        name.

        :param: The generic name.

        :returns: List of the required compiler flags.

        :raises KeyError: if the specified generic name is not defined
            for the compiler.
        """
        result = self._generic_flags.get(generic_name, None)
        if result is not None:
            return result
        raise KeyError(f"Generic flag name '{generic_name}' is not defined "
                       f"for '{self}'.")

    def __setitem__(self,
                    generic_name: str,
                    flags: Union[str, list[str]]) -> None:
        """
        Sets or updates a specified compiler-specific flag for
        a given generic name.

        :param generic_name: The generic name to set or update.
        :param flags: The flag or list of flags to use.
        """
        if isinstance(flags, list):
            self._generic_flags[generic_name] = flags
        else:
            self._generic_flags[generic_name] = [flags]

    @property
    def flags(self) -> ProfileFlags:
        ''':returns: the profile flags for this tool.'''
        return self._flags

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        ''':returns: the flags to be used with this tool.'''
        return self.flags.get_flags(config, file_path)

    def add_flags(self,
                  new_flags: Union[AbstractFlags, str, list[str]],
                  profile: Optional[str] = None):
        '''Adds the specified flags to the list of flags.

        :param new_flags: A single string or list of strings which are the
            flags to be added.
        '''
        self._flags.add_flags(new_flags, profile)

    def define_profile(self,
                       name: str,
                       inherit_from: Optional[str] = None):
        '''Defines a new profile name, and allows to specify if this new
        profile inherit settings from an existing profile.

        :param name: Name of the profile to define.
        :param inherit_from: Optional name of a profile to inherit
            settings from.
        '''
        self._flags.define_profile(name, inherit_from)

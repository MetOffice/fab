##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for a tool with flags.
It is the base class for compiler, linker, and pre-processor.

"""

from pathlib import Path
from typing import List, Optional, TYPE_CHECKING, Union

from fab.tools.category import Category
from fab.tools.flags import AbstractFlags, ProfileFlags
from fab.tools.tool import Tool

if TYPE_CHECKING:
    from fab.build_config import BuildConfig


class ToolWithFlags(Tool):
    '''This is the base class for all tools that provide flags.
    Note that the run method of the Tool base class is not overwritten
    to provide the flags to the base class, that needs to be done
    by the individual derived tools.

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
                                                List[str]]] = None) -> None:

        super().__init__(name, exec_name, category, availability_option)
        self._flags = ProfileFlags()

    @property
    def flags(self) -> ProfileFlags:
        ''':returns: the profile flags for this tool.'''
        return self._flags

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> List[str]:
        ''':returns: the flags to be used with this tool.'''
        return self.flags.get_flags(config, file_path)

    def add_flags(self,
                  new_flags: Union[AbstractFlags, str, List[str]],
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

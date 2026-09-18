##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''
This file contains the ProfileFlag class used to manage command line flags
for tools, especially path-specific flags for compiler. A ProfileFlag
manages flags for specific profiles, including inheritance.

Each tool uses a ProfileFlags instance. At runtime, the compilation steps
will use the selected profile to get the Flags inProfileFlags:
    Manages a set of flags for specific profiles, including inheritance.
stance to use.
The function `get_flags` will resolve the list of AbstractFlags by
converting them from left to right into a list of strings. For example,
[AlwaysFlag("-g"), ContainFlags("-O3", pattern="special_file")]
will be convert to `["-g", "-O3"]` if the file contains the string
`special_file`, and otherwise it will be `["-g"]`.

'''

import logging
from pathlib import Path
from typing import Optional, Union

from fab.tools.flags import AbstractFlags, FlagList
from fab.util import string_checksum

from fab.build_config import BuildConfig

logger = logging.getLogger(__name__)


class ProfileFlags:
    '''A list of flags that support a 'profile' to be used. If no profile is
    specified, it will use "" (empty string) as 'profile'. If a profile
    is defined without an explicit inherit, this dummy profile "" will be
    used (which implies that any flags specified with a profile will
    eventually be used by any profile, so it's an implicit, common base class.

    All functions take an optional profile parameter, so this class can also
    be used for tools that do not need a profile.

    :param flags: optional flags to be added to this profile.
    :param profile: optional profile to use if flags are specified,
        defaults to "".
    '''

    # This dictionary stores inheritance, where one mode
    # 'inherits' the flags from a different mode (recursively). To
    # avoid having to handle "" as special case, it is added here
    # as an always available dummy profile.
    _inherit_from: dict[str, str] = {"": ""}

    def __init__(self,
                 flags: Optional[Union[AbstractFlags, str, list[str]]] = None,
                 profile: str = "") -> None:
        # Stores the flags for each profile mode. The key is the (lower case)
        # name of the profile mode, and it contains a list of flags.
        # Initialise the dict with the default (empty) profile
        self._profiles: dict[str, FlagList] = {"": FlagList()}

        if profile != "":
            ProfileFlags.define_profile(profile)
        if flags:
            self.add_flags(flags, profile)

    @classmethod
    def define_profile(cls,
                       name: str,
                       inherit_from: Optional[str] = None):
        '''Defines a new profile name, and allows to specify if this new
        profile inherit settings from an existing profile. If inherit_from
        is specified, the newly defined profile will inherit from an existing
        profile (including the default profile "").

        :param name: Name of the profile to define.
        :param inherit_from: Optional name of a profile to inherit
            settings from.
        '''
        name = name.lower()
        if name in cls._inherit_from:
            raise KeyError(f"Profile '{name}' is already defined.")

        if inherit_from is not None:
            inherit_from = inherit_from.lower()
            if inherit_from not in cls._inherit_from:
                raise KeyError(f"Inherited profile '{inherit_from}' is "
                               f"not defined.")
            cls._inherit_from[name] = inherit_from
        else:
            cls._inherit_from[name] = ""

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        '''
        This method returns the flags used for the specified file,
        i.e. it will support path-specific flags. The BuildConfig
        is added as parameter to get the profile, but also to
        allow flags to use templated expressions `$relative` and
        `$output` (the values are taken from the config object).

        :param config: the build config object. It stores the selected
            compilation profile, and paths that can be used in templated
            expressions.
        :param file_path: path to the source file to compile.
        '''

        if config:
            profile = config.profile
        else:
            profile = ""

        all_flags = self[profile]

        resolved_flags = []
        for flags in all_flags:
            resolved_flags.extend(flags.get_flags(config, file_path))

        return resolved_flags

    def __getitem__(self,
                    profile: Optional[str] = None) -> list[AbstractFlags]:
        '''Returns the flags for the requested profile. If profile is not
        specified, the empty profile ("") will be used. It will also take
        inheritance into account, so add flags (recursively) from inherited
        profiles. But this function will not resolve the flags, i.e. replace
        the AbstractFlags instances with a list of strings.

        :param profile: the optional profile to use.

        :raises KeyError: if a profile is specified it is not defined
        '''
        if profile is None:
            profile = ""
        else:
            profile = profile.lower()

        if profile and profile not in ProfileFlags._inherit_from:
            raise KeyError(f"Profile '{profile}' is not defined")

        # First add any flags that we inherit. This will recursively call
        # this __getitem__ to resolve inheritance chains.

        if profile:
            inherit_from = self._inherit_from[profile]
            flags = self[inherit_from][:]
        else:
            flags = []
        # Now add the flags from this ProfileFlags. Note if no profile
        # is specified, "" will be used as key, and this is always
        # defined in the constructor of this object, so it will never
        # raise an exception in this case
        if profile.lower() in self._profiles:
            flags.extend(self._profiles[profile])
        return flags

    def add_flags(self,
                  new_flags: Union[AbstractFlags, str, list[str]],
                  profile: Optional[str] = None) -> None:
        '''Adds the specified flags to the list of flags.

        :param new_flags: A single string or list of strings which are the
            flags to be added.
        '''
        if profile is None:
            profile = ""
        else:
            profile = profile.lower()

        if profile and profile not in ProfileFlags._inherit_from:
            raise KeyError(f"add_flags: Profile '{profile}' is not defined.")

        if profile not in self._profiles:
            self._profiles[profile] = FlagList()

        if isinstance(new_flags, str):
            new_flags = [new_flags]

        self._profiles[profile].add_flags(new_flags)

    def remove_flag(self,
                    remove_flag: str,
                    profile: Optional[str] = None,
                    has_parameter: bool = False):
        '''Removes all occurrences of `remove_flag` in flags.
        If `has_parameter` is defined, the next entry in flags will also be
        removed, and if this object contains this flag+parameter without space
        (e.g. `-J/tmp`), it will be correctly removed. Note that only the
        flag itself must be specified, you cannot remove a flag only if a
        specific parameter is given (i.e. `remove_flag="-J/tmp"` will not
        work if this object contains `[...,"-J", "/tmp"]`).

        :param remove_flag: the flag to remove
        :param has_parameter: if the flag to remove takes a parameter
        '''

        if not profile:
            profile = ""
        else:
            profile = profile.lower()

        if profile not in self._profiles:
            raise KeyError(f"remove_flag: Profile '{profile}' is not defined.")

        self._profiles[profile].remove_flag(remove_flag, has_parameter)

    def checksum(self,
                 config: Optional["BuildConfig"] = None,
                 file_path: Optional[Path] = None) -> int:
        """
        :param config: the config object (used for templating)
        :param file_path: the file path of the source file, used for
            path-specific flags.

        :returns: a checksum of the flags.
        """

        if not file_path:
            # If no path, provide a dummy path
            file_path = Path()
        if config:
            profile = config.profile
        else:
            profile = ""

        if profile not in self._profiles:
            raise KeyError(f"checksum: Profile '{profile}' is "
                           f"not defined.")

        resolve_flags: list[str] = self.get_flags(config, file_path)
        return string_checksum(str(resolve_flags))

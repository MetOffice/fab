##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''This file contains a simple Flag class to manage tool flags.
It will need to be combined with build_config.FlagsConfig in a follow up
PR.
'''

import logging
from typing import Dict, List, Optional, Union
import warnings

from fab.util import string_checksum


class Flags(list):
    '''This class represents a list of parameters for a tool. It is a
    list with some additional functionality.

    TODO #22: This class and build_config.FlagsConfig should be combined.

    :param list_of_flags: List of parameters to initialise this object with.
    '''

    def __init__(self, list_of_flags: Optional[List[str]] = None):
        self._logger = logging.getLogger(__name__)
        super().__init__()
        if list_of_flags:
            self.extend(list_of_flags)

    def checksum(self) -> str:
        """
        :returns: a checksum of the flags.

        """
        return string_checksum(str(self))

    def add_flags(self, new_flags: Union[str, List[str]]):
        '''Adds the specified flags to the list of flags.

        :param new_flags: A single string or list of strings which are the
            flags to be added.
        '''

        if isinstance(new_flags, str):
            self.append(new_flags)
        else:
            self.extend(new_flags)

    def remove_flag(self, remove_flag: str, has_parameter: bool = False):
        '''Removes all occurrences of `remove_flag` in flags.
        If has_parameter is defined, the next entry in flags will also be
        removed, and if this object contains this flag+parameter without space
        (e.g. `-J/tmp`), it will be correctly removed. Note that only the
        flag itself must be specified, you cannot remove a flag only if a
        specific parameter is given (i.e. `remove_flag="-J/tmp"` will not
        work if this object contains `[...,"-J", "/tmp"]`).

        :param remove_flag: the flag to remove
        :param has_parameter: if the flag to remove takes a parameter
        '''

        # TODO #313: Check if we can use an OrderedDict and get O(1)
        # behaviour here (since ordering of flags can be important)
        i = 0
        flag_len = len(remove_flag)
        while i < len(self):
            flag = self[i]
            # First check for the flag stand-alone, i.e. if it has a parameter,
            # it will be the next entry: [... "-J", "/tmp"]:
            if flag == remove_flag:
                if has_parameter and i + 1 == len(self):
                    # We have a flag which takes a parameter, but there is no
                    # parameter. Issue a warning:
                    self._logger.warning(f"Flags '{' '. join(self)}' contain "
                                         f"'{remove_flag}' but no parameter.")
                    del self[i]
                else:
                    # Delete the argument and if required its parameter
                    del self[i:i+(2 if has_parameter else 1)]
                warnings.warn(f"Removing managed flag '{remove_flag}'.")
                continue
            # Now check if it has flag and parameter as one argument (-J/tmp)
            # ['-J/tmp'] and remove_flag('-J', True)
            if has_parameter and flag[:flag_len] == remove_flag:
                # No space between flag and parameter, remove this one flag
                warnings.warn(f"Removing managed flag '{remove_flag}'.")
                del self[i]
                continue
            i += 1


class ProfileFlags:
    '''A list of flags that support a 'profile' to be used. If no profile is
    specified, it will use "" (empty string) as 'profile'. All functions take
    an optional profile parameter, so this class can also be used for tools
    that do not need a profile.
    '''

    def __init__(self: "ProfileFlags"):
        # Stores the flags for each profile mode. The key is the (lower case)
        # name of the profile mode, and it contains a list of flags
        self._profiles: Dict[str, Flags] = {"": Flags()}

        # This dictionary stores an optional inheritance, where one mode
        # 'inherits' the flags from a different mode (recursively)
        self._inherit_from: Dict[str, str] = {}

    def __getitem__(self, profile: Optional[str] = None) -> List[str]:
        '''Returns the flags for the requested profile. If profile is not
        specified, the empty profile ("") will be used. It will also take
        inheritance into account, so add flags (recursively) from inherited
        profiles.

        :param profile: the optional profile to use.

        :raises KeyError: if a profile is specified it is not defined
        '''
        if profile is None:
            profile = ""
        else:
            profile = profile.lower()

        # First add any flags that we inherit. This will recursively call
        # this __getitem__ to resolve inheritance chains.
        if profile in self._inherit_from:
            inherit_from = self._inherit_from[profile]
            flags = self[inherit_from][:]
        else:
            flags = []
        # Now add the flags from this ProfileFlags. Note if no profile
        # is specified, "" will be used as key, and this is always
        # defined in the constructor of this object, so it will never
        # raise an exception in this case
        try:
            flags.extend(self._profiles[profile])
        except KeyError as err:
            raise KeyError(f"Profile '{profile}' is not defined.") from err

        return flags

    def define_profile(self,
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
        if name in self._profiles:
            raise KeyError(f"Profile '{name}' is already defined.")
        self._profiles[name.lower()] = Flags()

        if inherit_from is not None:
            if inherit_from not in self._profiles:
                raise KeyError(f"Inherited profile '{inherit_from}' is "
                               f"not defined.")
            self._inherit_from[name.lower()] = inherit_from.lower()

    def add_flags(self,
                  new_flags: Union[str, List[str]],
                  profile: Optional[str] = None):
        '''Adds the specified flags to the list of flags.

        :param new_flags: A single string or list of strings which are the
            flags to be added.
        '''
        if profile is None:
            profile = ""
        else:
            profile = profile.lower()

        if profile not in self._profiles:
            raise KeyError(f"add_flags: Profile '{profile}' is not defined.")

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

    def checksum(self, profile: Optional[str] = None) -> str:
        """
        :returns: a checksum of the flags.

        """
        if not profile:
            profile = ""
        else:
            profile = profile.lower()

        if profile not in self._profiles:
            raise KeyError(f"checksum: Profile '{profile}' is not defined.")

        return self._profiles[profile].checksum()

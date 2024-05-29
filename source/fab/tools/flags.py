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
from typing import List, Optional
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

    def remove_flag(self, remove_flag: str, has_parameter: bool = False):
        '''Removes all occurrences of `remove_flag` in flags`.
        If has_parameter is defined, the next entry in flags will also be
        removed, and if this object contains this flag+parameter without space
        (e.g. `-J/tmp`), it will be correctly removed. Note that only the
        flag itself must be specified, you cannot remove a flag only if a
        specific parameter is given (i.e. `remove_flag="-J/tmp"` will not
        work if this object contains `[...,"-J", "/tmp"]`).

        :param remove_flag: the flag to remove
        :param has_parameter: if the flag to remove takes a parameter
        '''
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

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''
This file contains the flag classes used to manage command line flags
for tools, especially path-specific flags for compiler.

AbstractFlags:
    The base class for a set of flags.

AlwaysFlags(AbstractFlags):
    Flags that will always apply, independent of the path of the
    file to be compiled. It provides Python Template functionality:

    - `$source` for *<project workspace>/source*
    - `$output` for *<project workspace>/build_output*
    - `$relative` for *<the source file's folder>*

MatchFlags(AlwaysFlags)
    Flags that are only applied if a wildcard search matches the
    source file. This will likely require to make sure that the full
    path is specified (or the pattern starts with `*`).

ContainFlags(AlwaysFlags)
    Flags that are only applied if the file path contains the specified
    string. The difference to MatchFlags is that ContainFlags do not
    need the full path to be specified.

FlagList:
    Manages a list of flags, each of which is an instance of an AbstractFlag.

Each tool uses a ProfileFlags instance. At runtime, the compilation steps
will use the selected profile to get the Flags instance to use.
The function `get_flags` will resolve the list of AbstractFlags by
converting them from left to right into a list of strings. For example,
[AlwaysFlag("-g"), ContainFlags("-O3", pattern="special_file")]
will be convert to `["-g", "-O3"]` if the file contains the string
`special_file`, and otherwise it will be `["-g"]`.

'''

from abc import ABC, abstractmethod
from fnmatch import fnmatch
import logging
from pathlib import Path
from string import Template
from typing import Optional, Union
import warnings

from fab.util import string_checksum

from fab.build_config import AddFlags, BuildConfig

logger = logging.getLogger(__name__)


class AbstractFlags(ABC):
    '''
    An abstract class to act as base class for all flag classes.
    '''

    @abstractmethod
    def __init__(self) -> None:
        """
        Dummy constructor.
        """

    @abstractmethod
    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        This function returns the list of flags to be used for the given
        filename.

        :param config: the config object (required for paths in templated
            strings)
        :param file_path: the file path of the file. This might not be used
            in all implementations.

        :returns: the list of flags to use.
        """

    @abstractmethod
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


class AlwaysFlags(AbstractFlags):
    """
    This class represents a list of flags that is always to be used,
    independent of the path of the source file. It also provides
    template functionality. This class also acts as convenient base
    class for all applications that add path-independent flags.

    :param flags: a string or list of strings with command line flags.
    """
    def __init__(self, flags: Optional[Union[str, list[str]]] = None) -> None:

        super().__init__()   # type: ignore[safe-super]
        if isinstance(flags, str):
            self._flags = [flags]
        elif flags:
            # Make a copy in case the user modifies the list later
            self._flags = flags[:]
        else:
            self._flags = []

    @staticmethod
    def replace_template(string_list: list[str],
                         config: Optional["BuildConfig"] = None,
                         file_path: Optional[Path] = None) -> list[str]:
        """This function replaces all `$relative`, `$source`, and `$output`
        in the string or list of string with the values taken from
        the config object and the file path.
        It is implemented as an abstract method (instead of acting on
        self._flags) since templating is also supported in patterns, to
        the same code here can be re-used).

        :param string_list: list of strings, which will get all template
            arguments replaced.
        :param config: the build configuration object from which paths
            are taken.
        :param file_path: the file path of an argument, used for `$source`.

        :returns: a new list with strings where all the template parameters
            have been removed.
        """
        params = {}
        if config:
            params['source'] = config.source_root
            params['output'] = config.build_output
        else:
            params['source'] = Path("/")
            params['output'] = Path("/")
        if file_path:
            params['relative'] = file_path.parent
        else:
            params['relative'] = Path(".")

        # Use templating to render any relative paths in our flags
        return [Template(i).substitute(params) for i in string_list]

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        This function returns the list of flags to be used for the given
        filename. This class will not take the file path into account,
        but it does support templated expressions `$relative`, `$source`,
        and `$output`.

        :param config: the config object (used for paths in templates)
        :param file_path: the file path of the file, not used in this
            class.

        :returns: the list of flags to use.
        """
        return AlwaysFlags.replace_template(self._flags, config, file_path)

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

        i = 0
        flag_len = len(remove_flag)
        while i < len(self._flags):
            flag = self._flags[i]
            # First check for the flag stand-alone, i.e. if it has a parameter,
            # it will be the next entry: [... "-J", "/tmp"]:
            if flag == remove_flag:
                if has_parameter and i + 1 == len(self._flags):
                    # We have a flag which takes a parameter, but there is no
                    # parameter. Issue a warning:
                    logger.warning(f"Flags '{' '. join(self._flags)}'"
                                   f" contain '{remove_flag}' but no "
                                   f"parameter.")
                    del self._flags[i]
                else:
                    # Delete the argument and if required its parameter
                    del self._flags[i:i+(2 if has_parameter else 1)]
                warnings.warn(f"Removing managed flag '{remove_flag}'.")
                continue
            # Now check if it has flag and parameter as one argument (-J/tmp)
            # ['-J/tmp'] and remove_flag('-J', True)
            if has_parameter and flag[:flag_len] == remove_flag:
                # No space between flag and parameter, remove this one flag
                warnings.warn(f"Removing managed flag '{remove_flag}'.")
                del self._flags[i]
                continue
            i += 1


class MatchFlags(AlwaysFlags):
    """
    This class implements path-specific flags using a file system
    wild card expressions (e.g. supporting `*` and `?`). It does support
    templated expressions `$relative`, `$source`, and `$output` in the
    pattern as well.

    :param pattern: the wildcard pattern which is used when matching.
    :param flags: a string or list of strings with command line flags.
    """
    def __init__(self,
                 pattern: str,
                 flags: Union[str, list[str]]) -> None:
        super().__init__(flags)
        self._pattern = pattern

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        This function returns the list of flags to be used for the given
        filename if the specified file path matches the pattern specified.

        :param config: the config object (used for paths in templates)
        :param file_path: the file path of the file that must match the
            specified wildcard pattern.

        :returns: the list of flags to use.
        """
        # Resolve the pattern template:
        pattern = self.replace_template([self._pattern], config, file_path)[0]
        # If there is no wildcard match, return an empty list
        if not fnmatch(str(file_path), pattern):
            return []

        return super().get_flags(config, file_path)


class ContainFlags(AlwaysFlags):
    """
    This class implements path-specific flags using a simple
    substring search.

    :param flags: a string or list of strings with command line flags.
    :param pattern: the substring which is used when matching.
    """

    def __init__(self,
                 pattern: str,
                 flags: Union[str, list[str]]) -> None:
        super().__init__(flags)
        self._pattern = pattern

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        This function returns the list of flags to be used for the given
        filename if the specified file path contains the pattern as
        a substrings (i.e. anywhere in the file path).

        :param config: the config object (used for paths in templates)
        :param file_path: the file path of the file that must match the
            specified wildcard pattern.

        :returns: the list of flags to use.
        """

        # Resolve the pattern template:
        pattern = self.replace_template([self._pattern], config, file_path)[0]
        # If pattern is not in the file path, return an empty list
        if pattern not in str(file_path):
            return []

        return super().get_flags(config, file_path)


class FlagList(list[AbstractFlags]):
    '''This class represents a list of parameters for a tool. It is a
    list with some additional functionality.

    :param list_of_flags: List of parameters to initialise this object with.
    :param add_flags: List of old-style AddFlags, which will be converted
        to the new MatchFlags.
    '''

    def __init__(
            self,
            list_of_flags: Optional[Union[AbstractFlags, str,
                                          list[str]]] = None,
            add_flags: Optional[Union[AddFlags,
                                      list[AddFlags]]] = None) -> None:
        self._logger = logging.getLogger(__name__)
        super().__init__()
        if isinstance(list_of_flags, (str, list)):
            self.append(AlwaysFlags(list_of_flags))
        elif list_of_flags:
            self.append(list_of_flags)
        if add_flags:
            if isinstance(add_flags, AddFlags):
                add_flags = [add_flags]
            # Convert old-style AddFlags to the new MatchFlags:
            for add_flag in add_flags:
                self.add_flags(MatchFlags(add_flag.match,
                                          add_flag.flags))

    def get_flags(self,
                  config: Optional["BuildConfig"] = None,
                  file_path: Optional[Path] = None) -> list[str]:
        """
        :returns: the flags to be used for the compilation profile and
            file path specified.
        """

        if not file_path:
            # If no path, provide a dummy path
            file_path = Path()

        all_flags_resolved: list[str] = []

        for flags in self:
            all_flags_resolved.extend(flags.get_flags(config, file_path))

        return all_flags_resolved

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

        resolve_flags: list[str] = self.get_flags(config, file_path)
        return string_checksum(str(resolve_flags))

    def add_flags(self,
                  new_flags: Union[AbstractFlags, str, list[str]]) -> None:
        '''Adds the specified flags to the list of flags.

        :param new_flags: New flags to be added. Can be either an class
            derived from AbstractFlags, a single string or list of strings.
        '''

        if isinstance(new_flags, AbstractFlags):
            self.append(new_flags)
        else:
            self.append(AlwaysFlags(new_flags))

    def remove_flag(self, remove_flag: str, has_parameter: bool = False):
        '''Removes all occurrences of `remove_flag` in flags.
        If `has_parameter` is defined, the next entry in flags will also be
        removed, and if this object contains this flag+parameter without space
        (e.g. `-J/tmp`), it will be correctly removed. Note that only the
        flag itself must be specified, you cannot remove a flag only if a
        specific parameter is given (i.e. `remove_flag="-J/tmp"` will not
        work if this object contains `[...,"-J", "/tmp"]`).

        This function will just call all individual flag objects to remove
        the flag. Note that a flag and its parameter cannot be split into
        two Flag instances (i.e. [AlwaysFlag("-J"), AlwaysFlag("/tmp")]
        will not work).

        :param remove_flag: the flag to remove
        :param has_parameter: if the flag to remove takes a parameter
        '''

        for flags in self:
            flags.remove_flag(remove_flag, has_parameter)

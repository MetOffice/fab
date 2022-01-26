from collections import namedtuple
from typing import List, Optional, NamedTuple

from fab.steps import Step


class ConfigSketch(object):
    def __init__(self, project_name, workspace,
                 grab_config, extract_config, steps: List[Step]):

        self.steps = steps
        self.project_name = project_name
        self.workspace = workspace
        self.grab_config = grab_config
        self.extract_config = extract_config


class PathFilter(object):
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include = include

    def check(self, path):
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


class AddPathFlags(NamedTuple):
    flags: List[str]
    path_filter: str = ""


class FlagsConfig(object):
    """
    Return flags for a given path. Contains a list of PathFlags.

    Multiple path filters can match a given path.
    For now, simply allows appending flags but will likely evolve to replace or remove flags.

    """
    def __init__(self, common_flags=None, all_path_flags=None):
        self.common_flags: List[str] = common_flags or []
        self.all_path_flags: List[AddPathFlags] = all_path_flags or []

    def flags_for_path(self, path):
        flags_for_path = [*self.common_flags]
        for path_flags in self.all_path_flags:
            if not path_flags.path_filter or path_flags.path_filter in str(path):
                flags_for_path += path_flags.flags
        return flags_for_path


# def flags_from_file_system(path):
#     # we think we'll need sys admin config, possibly from the file system
#     pass

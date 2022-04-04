##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from fnmatch import fnmatch
from multiprocessing import cpu_count
from pathlib import Path
from string import Template
from typing import List, Set

from fab.constants import BUILD_OUTPUT, SOURCE_ROOT
from fab.steps import Step


class Config(object):

    def __init__(self, label, workspace,
                 grab_config=None, steps: List[Step] = None,
                 use_multiprocessing=True, n_procs=max(1, cpu_count() - 1), debug_skip=False):
        self.label = label
        self.workspace = workspace

        # source config
        self.grab_config: Set = grab_config or set()
        # file_filtering = file_filtering or []
        # self.path_filters: List[PathFilter] = [PathFilter(*i) for i in file_filtering]

        # build steps
        self.steps: List[Step] = steps or []  # default, zero-config steps here

        # step run config
        self.use_multiprocessing = use_multiprocessing
        self.n_procs = n_procs
        self.debug_skip = debug_skip


class PathFilter(object):
    """
    Determines whether a given path should be included or excluded.

    """
    def __init__(self, path_filters, include):
        self.path_filters = path_filters
        self.include: bool = include

    def check(self, path):
        """Return the include flag if any of our path filters match the given path.

        The include can be True or False.
        If the flag does not match, return None ("nothing to say").

        """
        if any(i in str(path) for i in self.path_filters):
            return self.include
        return None


class AddFlags(object):
    """
    Add flags when our path filter matches.

    For example, add an include path for certain sub-folders.

    """

    def __init__(self, match: str, flags: List[str]):
        self.match: str = match
        self.flags: List[str] = flags

    def run(self, fpath: Path, input_flags: List[str], workspace: Path):
        """
        See if our filter matches the incoming file. If it does, add our flags.

        """
        params = {'relative': fpath.parent, 'source': workspace / SOURCE_ROOT, 'output': workspace / BUILD_OUTPUT}

        # does the file path match our filter?
        # mypy forces us to turn a path into a string when calling fnmatch (which works with paths)
        if not self.match or fnmatch(str(fpath), Template(self.match).substitute(params)):
            # use templating to render any relative paths in our flags
            add_flags = [Template(flag).substitute(params) for flag in self.flags]

            # add our flags
            input_flags += add_flags


class FlagsConfig(object):
    """
    Return flags for a given path. Contains a list of PathFlags.

    Multiple path filters can match a given path.
    For now, simply allows appending flags but will likely evolve to replace or remove flags.

    """

    def __init__(self, common_flags=None, path_flags: List[AddFlags] = None):
        self.common_flags = common_flags or []
        self.path_flags = path_flags or []

    def flags_for_path(self, path, workspace):
        # We COULD make the user pass these template params to the constructor
        # but we have a design requirement to minimise the config burden on the user,
        # so we take care of it for them here instead.
        params = {'source': workspace / SOURCE_ROOT, 'output': workspace / BUILD_OUTPUT}
        flags = [Template(i).substitute(params) for i in self.common_flags]

        for flags_modifier in self.path_flags:
            flags_modifier.run(path, flags, workspace=workspace)

        return flags

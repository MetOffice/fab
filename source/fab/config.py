from fnmatch import fnmatch
from multiprocessing import cpu_count
from string import Template
from pathlib import Path
from typing import List, Set

from fab.constants import BUILD_SOURCE, BUILD_OUTPUT

from fab.steps import Step


class ConfigSketch(object):
    def __init__(self, label, workspace,
                 grab_config=None, extract_config=None, steps: List[Step]=None,
                 use_multiprocessing=True, n_procs=max(1, cpu_count() - 1), debug_skip=False):

        self.label = label
        self.workspace = workspace

        # source config
        self.grab_config: Set = grab_config or set()
        self.extract_config: List = extract_config or []

        # build steps
        self.steps: List[Step] = steps or []  # default, zero-config steps here

        # step run config
        self.use_multiprocessing = use_multiprocessing
        self.n_procs = n_procs
        self.debug_skip = debug_skip


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
        params = {'relative': fpath.parent, 'source': workspace/BUILD_SOURCE, 'output': workspace/BUILD_OUTPUT}

        # does the file path match our filter?
        if not self.match or fnmatch(fpath, Template(self.match).substitute(params)):

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
    def __init__(self, common_flags=None, path_flags: List[AddFlags]=None):
        self.common_flags = common_flags or []
        self.path_flags = path_flags or []

    def flags_for_path(self, path, workspace):

        # We COULD make the user pass these template params to the constructor
        # but we have a design requirement to minimise the config burden on the user,
        # so we take care of it for them here instead.
        params = {'source': workspace / BUILD_SOURCE, 'output': workspace / BUILD_OUTPUT}
        flags = [Template(i).substitute(params) for i in self.common_flags]

        for flags_modifier in self.path_flags:
            flags_modifier.run(path, flags, workspace=workspace)

        return flags

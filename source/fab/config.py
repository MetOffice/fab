from fnmatch import fnmatch
from string import Template
from pathlib import Path
from typing import List, Optional, NamedTuple

from fab.constants import BUILD_SOURCE, BUILD_OUTPUT

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


class AddPathFlags(object):
    """

    """

    workspace = None  # todo: a better way?

    def __init__(self, path_filter: str, flags: List[str]):
        # Use templating to render any source and output paths in the filter and flags.
        # todo: unify this stuff
        substitute = dict(source=self.workspace/BUILD_SOURCE, output=self.workspace/BUILD_OUTPUT)

        self.path_filter = Template(path_filter).substitute(substitute)
        # we use safe_substitute() here because $relative is not being substituted until runtime
        self.flags = [Template(flag).safe_substitute(substitute) for flag in flags]

        # turn the flags back into templates for further substitution in do(),
        # because they can have the $relative symbol in them
        self.flags = [Template(flag) for flag in self.flags]

    def do(self, fpath: Path, flags: List[str]):
        """
        See if our filter matches the incoming file. If it does, add our flags.

        """

        # does the file path match our filter?
        if not self.path_filter or fnmatch(fpath, self.path_filter):

            # use templating to render any relative paths in our flags
            rendered_flags = [flag.substitute(relative=fpath.parent) for flag in self.flags]

            # add our flags
            flags += rendered_flags


class FlagsConfig(object):
    """
    Return flags for a given path. Contains a list of PathFlags.

    Multiple path filters can match a given path.
    For now, simply allows appending flags but will likely evolve to replace or remove flags.

    """
    def __init__(self, workspace: Path, common_flags=None, all_path_flags=None):

        # render any templates in the common flags.
        substitute = dict(source=workspace / BUILD_SOURCE, output=workspace / BUILD_OUTPUT)
        self.common_flags: List[str] = [Template(i).substitute(substitute) for i in common_flags]

        # we leave the path flags template rendering inside AddPathFlags for now, at least.
        self.all_path_flags: List[AddPathFlags] = all_path_flags or []

    def flags_for_path(self, path):
        flags = [*self.common_flags]
        for foo in self.all_path_flags:
            foo.do(path, flags)

        return flags

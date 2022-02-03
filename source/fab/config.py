from fnmatch import fnmatch
from string import Template
from pathlib import Path
from typing import List

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


class AddFlags(object):
    """
    Add flags when our path filter matches.

    For example, add an include path for certain sub-folders.

    """
    workspace = None  # todo: a better way?

    def __init__(self, match: str, flags: List[str]):

        self.match: str = Template(match).substitute(
            source=self.workspace/BUILD_SOURCE, output=self.workspace/BUILD_OUTPUT)

        # we can't fully render this until runtime because it can contain $relative, which needs a file
        self.flags: List[Template] = [Template(flag) for flag in flags]

    def run(self, fpath: Path, flags: List[str]):
        """
        See if our filter matches the incoming file. If it does, add our flags.

        """
        # does the file path match our filter?
        if not self.match or fnmatch(fpath, self.match):

            # use templating to render any relative paths in our flags
            rendered_flags = [flag.substitute(
                relative=fpath.parent, source=self.workspace/BUILD_SOURCE, output=self.workspace/BUILD_OUTPUT)
                for flag in self.flags]

            # add our flags
            flags += rendered_flags


class FlagsConfig(object):
    """
    Return flags for a given path. Contains a list of PathFlags.

    Multiple path filters can match a given path.
    For now, simply allows appending flags but will likely evolve to replace or remove flags.

    """
    # todo: we should accept both config-friendly tuples and ready-made AddPathFlags objects here?
    def __init__(self, workspace: Path, common_flags=None, path_flags: List[AddFlags]=None):
        common_flags = common_flags or []

        # render any templates in the common flags.
        # we leave the path flags template rendering inside AddPathFlags for now, at least.
        substitute = dict(source=workspace / BUILD_SOURCE, output=workspace / BUILD_OUTPUT)
        self.common_flags: List[str] = [Template(i).substitute(substitute) for i in common_flags]
        self.path_flags = path_flags or []

    def flags_for_path(self, path):
        flags = [*self.common_flags]
        for flags_modifier in self.path_flags:
            flags_modifier.run(path, flags)

        return flags

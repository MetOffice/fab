# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import warnings
from abc import ABC
from pathlib import Path
from typing import Union, Dict, Tuple
import xml.etree.ElementTree as ET

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


def current_commit(folder=None):
    folder = folder or '.'
    output = run_command(['git', 'log', '--oneline', '-n', '1'], cwd=folder)
    commit = output.split()[0]
    return commit


class GrabGitBase(GrabSourceBase, ABC):
    """
    Base class for Git operations.

    """
    def run(self, artefact_store: Dict, config):
        if not self.tool_available():
            raise RuntimeError("git command line tool not available")
        super().run(artefact_store, config)

    def tool_available(self) -> bool:
        """Is the command line git tool available?"""
        try:
            run_command(['git', 'help'])
        except FileNotFoundError:
            return False
        return True

    def is_working_copy(self, dst: Union[str, Path]) -> bool:
        """Is the given path is a working copy?"""
        try:
            run_command(['git', 'status'], cwd=dst)
        except RuntimeError:
            return False
        return True

    def fetch(self):
        command = ['git', 'fetch', '--depth', '1', self.src]
        if self.revision:
            command.append(self.revision)
        run_command(command, cwd=str(self._dst))


# todo: allow cli args, e.g to set the depth
class GitCheckout(GrabGitBase):
    """
    Checkout or update a Git repo.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # create folder?
        if not self._dst.exists():  # type: ignore
            self._dst.mkdir(parents=True)
            run_command(['git', 'init', '.'], cwd=self._dst)
        elif not self.is_working_copy(self._dst):  # type: ignore
            raise ValueError(f"destination exists but is not a working copy: '{self._dst}'")

        self.fetch()
        run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=self._dst)

        try:
            self._dst.relative_to(config.project_workspace)
            run_command(['git', 'clean', '-f'], cwd=self._dst)
        except ValueError:
            warnings.warn(f'not safe to clean git source in {self._dst}')


class GitMerge(GrabGitBase):
    """
    Merge a git repo into a local working copy.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)
        if not self._dst or not self.is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")

        self.fetch()
        run_command(['git', 'merge', self.revision], cwd=self._dst)
        self.check_conflict()

    def check_conflict(self):
        # check if there's a conflict
        xml_str = run_command([self.command, 'status', '--xml'], cwd=self._dst)
        root = ET.fromstring(xml_str)

        for target in root:
            if target.tag != 'target':
                continue
            for entry in target:
                if entry.tag != 'entry':
                    continue
                for element in entry:
                    if element.tag == 'wc-status' and element.attrib['item'] == 'conflicted':
                        raise RuntimeError(f'{self.command} merge encountered a conflict:\n{xml_str}')
        return False

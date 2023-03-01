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
    def __init__(self, src: Union[str, Path], dst: str, revision, name=None):
        """
        :param src:
            Such as `https://github.com/metomi/fab-test-data.git` or path to a local working copy.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            A branch, tag or commit.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src, dst, name=name, revision=revision)

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

    # def fetch(self) -> str:
    #     """
    #     Fetch the source url, adding a new remote if necessary.
    #
    #     Returns the remote alias.
    #
    #     """
    #     # todo: check it's a url not a path?
    #     remotes = get_remotes(self._dst)
    #     if self.src not in remotes.values():
    #         remote_name = self.add_remote()
    #     else:
    #         remote_name = [k for k, v in remotes.items() if v == self.src][0]
    #
    #     # ok it's a remote, we can fetch
    #     command = ['git', 'fetch', '--depth', '1', remote_name, self.revision]
    #     run_command(command)
    #
    #     return remote_name



# todo: allow cli args, e.g to set the depth
class GitCheckout(GrabGitBase):
    """
    Checkout or update a Git repo.

    If the revision is a branch or tag is provided, no extra branches or history is fetched.
    If the revision is a commit, the entire remote is fetched.

    """

    # todo: just fetch url refspec then checkout FETCH_HEAD


    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # new folder?
        if not self._dst.exists():  # type: ignore

            self._dst.mkdir(parents=True)
            run_command(['git', 'init', '.'], self._dst)

            try:
                run_command(['git', 'fetch', '--depth', '1', self.src, str(self.revision)], cwd=str(self._dst))
                run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=self._dst)

            except RuntimeError:
                # if it was a commit it will fail with github, so clone the whole repo and checkout the commit
                # todo: can we do this without pulling the whole repo? E.g find a branch containing the commit?
                warnings.warn('shallow git clone failed, retrying with full clone')
                run_command(['git', 'fetch', self.src], cwd=self._dst)
                run_command(['git', 'checkout', self.revision], cwd=self._dst)

        else:
            if self.is_working_copy(self._dst):  # type: ignore
                remote_name = self.fetch()
                run_command(['git', 'checkout', f'{remote_name}/{self.revision}'], cwd=self._dst)
                run_command(['git', 'reset', '--hard'], cwd=self._dst)
            else:
                # we can't deal with an existing folder that isn't a working copy
                raise ValueError(f"destination exists but is not an fcm working copy: '{self._dst}'")


class GitMerge(GrabGitBase):
    """
    Merge a git repo into a local working copy.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)
        if not self._dst or not self.is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")

        # we need to make sure the src is in the list of remotes

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

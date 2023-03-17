# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import warnings
from abc import ABC
from pathlib import Path
from typing import Union, Dict

from fab.steps import step_timer
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

def fetch(src, revision, dst):
    # todo: allow shallow fetch with --depth 1
    command = ['git', 'fetch', src]
    if revision:
        command.append(revision)

    run_command(command, cwd=str(dst))


# todo: allow cli args, e.g to set the depth
@step_timer
def git_checkout(config, src: str, dst_label: str = '', revision=None):
    """
    Checkout or update a Git repo.

    """
    _dst = config.source_root / dst_label

    # create folder?
    if not _dst.exists():
        _dst.mkdir(parents=True)
        run_command(['git', 'init', '.'], cwd=_dst)

    elif not is_working_copy(self._dst):  # type: ignore
        raise ValueError(f"destination exists but is not a working copy: '{_dst}'")

    fetch()
    run_command(['git', 'checkout', 'FETCH_HEAD'], cwd=_dst)

    try:
        _dst.relative_to(config.project_workspace)
        run_command(['git', 'clean', '-f'], cwd=_dst)
    except ValueError:
        warnings.warn(f'not safe to clean git source in {_dst}')


class GitMerge(GrabGitBase):
    """
    Merge a git repo into a local working copy.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)
        if not self._dst or not self.is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")

        self.fetch()

        try:
            run_command(['git', 'merge', 'FETCH_HEAD'], cwd=self._dst)
        except RuntimeError as err:
            run_command(['git', 'merge', '--abort'], cwd=self._dst)
            raise RuntimeError(f"Error merging {self.revision}. Merge aborted.\n{err}")

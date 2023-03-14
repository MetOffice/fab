# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import warnings
from abc import ABC
from pathlib import Path
from typing import Any, Union, Dict, Optional

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


def current_commit(folder: Optional[str] = None) -> str:
    folder = folder or '.'
    output = run_command(['git', 'log', '--oneline', '-n', '1'], cwd=folder)
    commit = output.split()[0]  # type: ignore # folder is a str
    return commit


class GrabGitBase(GrabSourceBase, ABC):
    """
    Base class for Git operations.

    """
    def run(self, artefact_store: Dict[Any, Any], config: Any) -> None:
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

    def fetch(self) -> None:
        # todo: allow shallow fetch with --depth 1
        command = ['git', 'fetch', self.src]
        if self.revision:
            command.append(self.revision)

        run_command(command, cwd=str(self._dst))


# todo: allow cli args, e.g to set the depth
class GitCheckout(GrabGitBase):
    """
    Checkout or update a Git repo.

    """
    def run(self, artefact_store: Dict[Any, Any], config: Any) -> None:
        super().run(artefact_store, config)

        # create folder?
        assert self._dst  # for mypy
        if not self._dst.exists():
            self._dst.mkdir(parents=True)
            run_command(['git', 'init', '.'], cwd=self._dst)
        elif not self.is_working_copy(self._dst):
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
    def run(self, artefact_store: Dict[Any, Any], config: Any) -> None:
        super().run(artefact_store, config)
        if not self._dst or not self.is_working_copy(self._dst):
            raise ValueError(f"destination is not a working copy: '{self._dst}'")

        self.fetch()

        try:
            run_command(['git', 'merge', 'FETCH_HEAD'], cwd=self._dst)
        except RuntimeError as err:
            run_command(['git', 'merge', '--abort'], cwd=self._dst)
            raise RuntimeError(f"Error merging {self.revision}. Merge aborted.\n{err}")

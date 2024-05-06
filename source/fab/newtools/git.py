##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for git.
"""

from pathlib import Path
from typing import Optional, Union

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Git(Tool):
    '''This is the base class for git.
    '''

    def __init__(self):
        super().__init__("git", "git", Categories.GIT)

    def check_available(self) -> bool:
        ''':returns: whether git is installed or not.'''
        try:
            self.run('help')
        except FileNotFoundError:
            return False
        return True

    def current_commit(self, folder=None) -> str:
        ''':returns the hash of the current commit.
        '''
        folder = folder or '.'
        output = self.run(['log', '--oneline', '-n', '1'], cwd=folder)
        commit = output.split()[0]
        return commit

    def is_working_copy(self, dst: Union[str, Path]) -> bool:
        """:returns: whether the given path is a working copy or not.
        """
        try:
            self.run(['status'], cwd=dst, capture_output=False)
        except RuntimeError:
            return False
        return True

    def fetch(self, src: Union[str, Path],
              dst: Union[str, Path],
              revision: Union[None | str]):
        '''Runs `git fetch` in the specified directory
        :param src: the source directory from which to fetch
        :param revision: the revision to fetch (can be "" for latest revision)
        :param dst: the directory in which to run fetch.
        '''
        # todo: allow shallow fetch with --depth 1
        command = ['fetch', str(src)]
        if revision:
            command.append(revision)
        self.run(command, cwd=str(dst))

    def checkout(self, src: str,
                 dst: str = '',
                 revision: Optional[str] = None):
        """
        Checkout or update a Git repo.
        :param src: the source directory from which to fetch.
        :param dst: the directory in which to run fetch.
        :param revision: the revision to fetch (can be "" for latest revision).
        """
        self.fetch(src, dst, revision)
        self.run(['checkout', 'FETCH_HEAD'], cwd=dst)

    def merge(self, dst: Union[str, Path],
              src: str,
              revision: Optional[str] = None):
        """
        Merge a git repo into a local working copy.
        """

        if not dst or not self.is_working_copy(dst):
            raise ValueError(f"destination is not a working copy: '{dst}'")

        self.fetch(src=src, revision=revision, dst=dst)

        try:
            self.run(['merge', 'FETCH_HEAD'], cwd=dst)
        except RuntimeError as err:
            self.run(['merge', '--abort'], cwd=dst)
            raise RuntimeError(f"Error merging {revision}. "
                               f"Merge aborted.\n{err}") from err


if __name__ == "__main__":
    git = Git()
    print(git.check_available())
    print(git.current_commit())

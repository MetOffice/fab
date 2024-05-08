##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

"""This file contains the base class for git.
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from fab.newtools.categories import Categories
from fab.newtools.tool import Tool


class Versioning(Tool):
    '''This is the base class for versioning tools like git and svn.
    :param name: the name of the tool.
    :param exec_name: the name of the executable of this tool.
    :param working_copy_command: which command is run to determine if
        a directory is a working copy for this tool or not.
    :param category: the category to which this tool belongs):
    '''

    def __init__(self, name: str,
                 exec_name: str,
                 working_copy_command: str,
                 category: Categories):
        super().__init__(name, exec_name, category)
        self._working_copy_command = working_copy_command

    def check_available(self) -> bool:
        ''':returns: whether this tool is installed or not.'''
        try:
            self.run("help")
        except RuntimeError:
            return False
        return True

    def is_working_copy(self, dst: Union[str, Path]) -> bool:
        """:returns: whether the given path is a working copy or not. It
        runs the command specific to the instance.
        """
        try:
            self.run([self._working_copy_command], cwd=dst,
                     capture_output=False)
        except RuntimeError:
            return False
        return True


# =============================================================================
class Git(Versioning):
    '''This is the base class for git.
    '''

    def __init__(self):
        super().__init__("git", "git",
                         "status",
                         Categories.GIT)

    def current_commit(self, folder=None) -> str:
        ''':returns the hash of the current commit.
        '''
        folder = folder or '.'
        output = self.run(['log', '--oneline', '-n', '1'], cwd=folder)
        commit = output.split()[0]
        return commit

    def fetch(self, src: Union[str, Path],
              dst: Union[str, Path],
              revision: Union[None, str]):
        '''Runs `git fetch` in the specified directory
        :param src: the source directory from which to fetch
        :param revision: the revision to fetch (can be "" for latest revision)
        :param dst: the directory in which to run fetch.
        '''
        # todo: allow shallow fetch with --depth 1
        command = ['fetch', str(src)]
        if revision:
            command.append(revision)
        self.run(command, cwd=str(dst), capture_output=False)

    def checkout(self, src: str,
                 dst: str = '',
                 revision: Optional[str] = None):
        """Checkout or update a Git repo.
        :param src: the source directory from which to fetch.
        :param dst: the directory in which to run fetch.
        :param revision: the revision to fetch (can be "" for latest revision).
        """
        self.fetch(src, dst, revision)
        self.run(['checkout', 'FETCH_HEAD'], cwd=dst, capture_output=False)

    def merge(self, dst: Union[str, Path],
              revision: Optional[str] = None):
        """Merge a git repo into a local working copy.
        """
        try:
            self.run(['merge', 'FETCH_HEAD'], cwd=dst, capture_output=False)
        except RuntimeError as err:
            self.run(['merge', '--abort'], cwd=dst, capture_output=False)
            raise RuntimeError(f"Error merging {revision}. "
                               f"Merge aborted.\n{err}") from err


# =============================================================================
class Subversion(Versioning):
    '''This is the base class for subversion.
    :param name: name of the tool, defaults to subversion.
    :param exec_name: name of the executable, defaults to "svn".
    '''

    def __init__(self, name: Optional[str] = None,
                 exec_name: Optional[str] = None,
                 category: Categories = Categories.SUBVERSION):
        name = name or "subversion"
        exec_name = exec_name or "svn"
        super().__init__(name, exec_name, "info", category)

    def execute(self, pre_commands: Optional[List[str]] = None,
                revision: Optional[Union[int, str]] = None,
                post_commands: Optional[List[str]] = None,
                env: Optional[Dict[str, str]] = None,
                cwd: Optional[Union[Path, str]] = None,
                capture_output=True) -> str:
        '''Executes a svn command.
        :param pre_commands:
            List of strings to be sent to :func:`subprocess.run` as the
            command.
        :param revision: optional revision number as argument
        :param post_commands:
            List of additional strings to be sent to :func:`subprocess.run`
            after the optional revision number.
        :param env:
            Optional env for the command. By default it will use the current
            session's environment.
        :param capture_output:
            If True, capture and return stdout. If False, the command will
            print its output directly to the console.
        '''
        command = []
        if pre_commands:
            command.extend(pre_commands)
        if revision:
            command.extend(["--revision", f"{revision}"])
        if post_commands:
            command.extend(post_commands)
        return super().run(command, env=env, cwd=cwd,
                           capture_output=capture_output)

    def export(self, src: Union[str, Path],
               dst: Union[str, Path],
               revision: Optional[str] = None):
        '''Runs svn export.
        :param src: from where to export.
        :param dst: destination path.
        :param revision: revision to export.
        '''
        self.execute(['export', '--force'], revision, [str(src), str(dst)])

    def checkout(self, src: Union[str, Path],
                 dst: Union[str, Path],
                 revision: Optional[str] = None):
        '''Runs svn checkout.
        :param src: from where to check out.
        :param dst: destination path.
        :param revision: revision to check out.
        '''
        self.execute(["checkout"], revision, [str(src), str(dst)])

    def update(self, dst: Union[str, Path],
               revision: Optional[str] = None):
        '''Runs svn checkout.
        :param dst: destination path.
        :param revision: revision to check out.
        '''
        self.execute(['update'], revision, cwd=dst)

    def merge(self, src: Union[str, Path],
              dst: Union[str, Path],
              revision: Optional[str] = None):
        '''Runs svn merge.
        '''
        # We seem to need the url and version combined for this operation.
        # The help for fcm merge says it accepts the --revision param, like
        # other commands, but it doesn't seem to be recognised.
        rev_url = f'{src}'
        if revision is not None:
            rev_url += f'@{revision}'

        self.execute(['merge', '--non-interactive', rev_url], cwd=dst)


# =============================================================================
class Fcm(Subversion):
    '''This is the base class for subversion.
    '''

    def __init__(self):
        super().__init__("fcm", "fcm", Categories.FCM)

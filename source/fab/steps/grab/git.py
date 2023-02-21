# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from abc import ABC
from pathlib import Path
from typing import Union, Dict, Tuple
import xml.etree.ElementTree as ET

from fab.steps.grab import GrabSourceBase
from fab.tools import run_command


class GrabGitBase(GrabSourceBase, ABC):
    """
    Base class for Git operations.

    """
    def __init__(self, src: str, dst: str, revision=None, name=None):
        """
        :param src:
            Such as `https://github.com/metomi/fab-test-data.git`.
        :param dst:
            The name of a sub folder, in the project workspace, in which to put the source.
            If not specified, the code is copied into the root of the source folder.
        :param revision:
            E.g 'vn6.3'.
        :param name:
            Human friendly name for logger output, with sensible default.

        """
        super().__init__(src, dst, name=name, revision=revision)

    def run(self, artefact_store: Dict, config):
        if not self.tool_available():
            raise RuntimeError("git command line tool not available")
        super().run(artefact_store, config)

    @classmethod
    def tool_available(cls) -> bool:
        """Is the command line tool available?"""
        try:
            run_command(['git', 'help'])
        except FileNotFoundError:
            return False
        return True

    # def _cli_revision_parts(self):
    #     # return the command line argument to specif the revision, if there is one
    #     return ['--branch', str(self.revision)] if self.revision is not None else []

    def is_working_copy(self, dst: Union[str, Path]) -> bool:
        # is the given path is a working copy?
        try:
            run_command(['git', 'status'], cwd=dst)
        except RuntimeError:
            return False
        return True


class GitExport(GrabGitBase):
    """
    Export a git repo folder to the project workspace.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        command = ['git', 'archive', '--remote', self.src]
        # todo untar
        assert False

        if self.revision:
            command.append(self.revision)

        run_command(command, str(self._dst))


class GitCheckout(GrabGitBase):
    """
    Checkout or update a Git repo.

    .. note::
        If the destination is a working copy, it will be updated to the given revision, **ignoring the source url**.
        As such, the revision should be provided via the argument, not as part of the url.

    """
    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        # new folder?
        if not self._dst.exists():  # type: ignore
            revision_parts = ['--branch', str(self.revision)] if self.revision is not None else []
            run_command([
                'git', 'clone',
                *revision_parts,
                self.src, str(self._dst)
            ])

        else:
            # working copy?
            if self.is_working_copy(self._dst):  # type: ignore
                # update
                # todo: ensure the existing checkout is from self.src?
                revision_parts = [str(self.revision)] if self.revision is not None else []
                run_command([
                    'git', 'checkout',
                    remote,
                    *revision_parts,
                ], cwd=self._dst)
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

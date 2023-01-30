# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Union, Dict

from fab.steps.grab import GrabSourceBase

try:
    import git
except ImportError:
    git = None  # type: ignore


class GrabGit(GrabSourceBase):
    """
    Grab a Git repo into the project workspace.

    A destination name must be specified because each git repo needs to be in a separate folder.

    .. note::

        A revision must be specified.
        If `shallow` is set (the default), then the revision should be a branch or tag.
        If `shallow` is not set, the revision can also be a commit hash.

    A `shallow` grab clones/fetches only the given revision, with no history.
    Otherwise, the full repo is cloned including all branches and history.

    Example::

        GrabGit(src='~/git/my_project', revision='v0.1b')
        GrabGit(src='https://github.com/me/my_project.git', revision='a1b2c3', shallow=False)

    """

    def __init__(self, src: Union[Path, str], dst: str = None,  # type: ignore
                 revision=None, shallow: bool = True, name=None):
        """
        Params as for :class:`~fab.steps.grab.GrabSourceBase`, plus the following.

        :param shallow:
            This flag causes the grab to be quick and shallow, fetching just the branch and no history.
            You may need to turn this off when fetching a commit hash.

        """
        if not revision:
            raise ValueError("GrabGit (currently) requires a revision to be specifed.")

        if not dst:
            raise ValueError("A destination name must be specified to GrabGit.")

        super().__init__(src=str(src), dst=dst, revision=revision, name=name)

        self.shallow = shallow

    def run(self, artefact_store: Dict, config):
        super().run(artefact_store, config)

        if not git:
            raise ImportError('git not installed, unable to continue')

        our_repo = self._fetch()
        ref = self._find_ref(our_repo)

        # point head to the revision reference and "checkout"
        our_repo.head.reference = ref
        our_repo.head.reset(index=True, working_tree=True)

    def _fetch(self):
        # fetch the branch/tag/commit
        fetch_args = [self.revision] if self.shallow else []
        fetch_kwargs = {'depth': 1, 'tags': True} if self.shallow else {'tags': True}

        if not self._dst.exists():  # type: ignore
            our_repo = git.Repo.init(self._dst, mkdir=True)
            our_repo.create_remote('origin', self.src)
        else:
            our_repo = git.Repo(self._dst)

        our_repo.remotes['origin'].fetch(*fetch_args, **fetch_kwargs)

        return our_repo

    def _find_ref(self, our_repo):
        # find the revision
        ref = None

        # try our branches & tags
        try:
            ref = our_repo.refs[self.revision]
        except IndexError:
            pass

        # try our commits
        if not ref:
            try:
                ref = our_repo.commit(self.revision)
            except git.BadName:
                pass

        # try the origin repo
        if not ref:
            try:
                origin_ref = our_repo.remotes['origin'].refs[self.revision]
                our_repo.create_head(self.revision, origin_ref.commit)
                ref = our_repo.refs[self.revision]
            except IndexError:
                pass

        if not ref:
            raise ValueError(f"can't find branch/tag/commit {self.revision}")
        return ref

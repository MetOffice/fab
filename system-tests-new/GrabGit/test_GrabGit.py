# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Test GrabGit.

Most tests are done from a local git repo archived in "tiny_fortran.tar", in this folder.
The repo contains a simple Fortran program which prints an integer variable, foo.

The repo has the following commit structure, each printing a different variable.
 - Head of branch main: foo = 1
 - Head of branch foo2: foo = 22
 - Preceding, tagged commit on foo2: foo = 2

With this we can test grabbing a branch, tag and commit.

"""
from pathlib import Path
from unittest import mock

import git
import pytest

from fab.util import run_command
from fab.steps.grab import GrabGit


MY_MOD = 'src/my_mod.F90'


class TestGrabGit_Local(object):

    def prep(self, tmp_path, revision, shallow: bool):
        repo_path = tmp_path / 'repo'
        repo_path.mkdir()
        run_command(['tar', '-xkf', str(Path(__file__).parent / 'tiny_fortran.tar')], cwd=repo_path)

        grab = GrabGit(src=repo_path / 'tiny_fortran', dst='tiny_fortran', revision=revision, shallow=shallow)
        config = mock.Mock(source_root=tmp_path / 'source')

        return grab, config

    # shallow clone (new folder) tests
    def test_shallow_clone_branch(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='foo2', shallow=True)
        grab.run(artefact_store=None, config=config)

        assert "foo = 22" in open(grab._dst / MY_MOD).read()
        # check it's shallow
        our_repo = git.Repo(grab._dst)
        assert len(our_repo.branches) == 1
        assert len(list(our_repo.iter_commits())) == 1

    def test_shallow_clone_tag(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='my_tag', shallow=True)
        grab.run(artefact_store=None, config=config)
        assert "foo = 2" in open(grab._dst / MY_MOD).read()

    def test_shallow_clone_commit(self, tmp_path):
        # We can't shallow grab a commit. Git won't let us.
        grab, config = self.prep(tmp_path, revision='15c0d5', shallow=True)
        with pytest.raises(git.GitCommandError):
            grab.run(artefact_store=None, config=config)

    # shallow update (existing folder) tests
    def test_shallow_update_branch(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='foo2', shallow=True)

        # first grab creates folder
        grab.run(artefact_store=None, config=config)

        # grab again, folder already exists
        grab.run(artefact_store=None, config=mock.Mock(source_root=tmp_path / 'source'))

        assert "foo = 22" in open(grab._dst / MY_MOD).read()

    def test_shallow_update_tag(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='my_tag', shallow=True)

        # first grab creates folder
        grab.run(artefact_store=None, config=config)

        # grab again, folder already exists
        grab.run(artefact_store=None, config=config)

        assert "foo = 2" in open(grab._dst / MY_MOD).read()

    # deep clone (new folder) tests
    def test_deep_clone_branch(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='foo2', shallow=False)
        grab.run(artefact_store=None, config=config)

        assert "foo = 22" in open(grab._dst / MY_MOD).read()

        # check it's deep
        our_repo = git.Repo(grab._dst)
        assert len(our_repo.remotes['origin'].refs) == 2
        assert len(list(our_repo.iter_commits())) == 4

    def test_deep_clone_tag(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='my_tag', shallow=False)
        grab.run(artefact_store=None, config=config)
        assert "foo = 2" in open(grab._dst / MY_MOD).read()

    def test_deep_clone_commit(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='15c0d5', shallow=False)
        grab.run(artefact_store=None, config=config)
        assert "foo = 2" in open(grab._dst / MY_MOD).read()

    # deep update (existing folder) tests
    def test_deep_update_branch(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='foo2', shallow=False)

        # first grab creates folder
        grab.run(artefact_store=None, config=config)

        # grab again, folder already exists
        grab.run(artefact_store=None, config=config)

        assert "foo = 22" in open(grab._dst / MY_MOD).read()

    def test_deep_update_tag(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='my_tag', shallow=False)

        # first grab creates folder
        grab.run(artefact_store=None, config=config)

        # grab again, folder already exists
        grab.run(artefact_store=None, config=config)

        assert "foo = 2" in open(grab._dst / MY_MOD).read()

    def test_deep_update_commit(self, tmp_path):
        grab, config = self.prep(tmp_path, revision='15c0d5', shallow=False)

        # first grab creates folder
        grab.run(artefact_store=None, config=config)

        # grab again, folder already exists
        grab.run(artefact_store=None, config=config)

        assert "foo = 2" in open(grab._dst / MY_MOD).read()


class TestGrabGitGithub(object):
    # Check we can grab from github.
    # There's no need to hit their servers lots of times just for our tests,
    # so we just have one small grab here. We could even remove this altogether.

    def test_vanilla(self, tmp_path):
        # todo: put this somewhere better, under MO control.
        tiny_fortran_github = 'https://github.com/bblay/tiny_fortran.git'
        grab = GrabGit(src=tiny_fortran_github, dst='tiny_fortran', revision='foo2', shallow=True)
        grab.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))

        my_mod = open(grab._dst / 'src/my_mod.F90').read()
        assert "foo = 22" in my_mod

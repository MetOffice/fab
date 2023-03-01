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
from unittest import mock

import pytest

from fab.steps.grab.git import current_branch, current_commit, GitCheckout
from fab.tools import run_command


# MY_MOD = 'src/my_mod.F90'
#
#
# class TestGitExport_Local(object):
#
#     def prep(self, tmp_path: Path, revision, shallow: bool, update=False):
#         repo_path = tmp_path / 'repo'
#
#         # when testing repo updates, there will already have been a preceding call to prep
#         if not update:
#             repo_path.mkdir()
#             run_command(['tar', '-xkf', str(Path(__file__).parent / 'tiny_fortran.tar')], cwd=repo_path)
#
#         grab = GitExport(src=repo_path / 'tiny_fortran', dst='tiny_fortran', revision=revision)
#         config = mock.Mock(source_root=tmp_path / 'source')
#
#         return grab, config
#
#     # shallow clone (new folder) tests
#     def test_shallow_clone_branch(self, tmp_path):
#         grab, config = self.prep(tmp_path, revision='foo2', shallow=True)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 22" in open(grab._dst / MY_MOD).read()
#         # check it's shallow
#         our_repo = git.Repo(grab._dst)
#         assert len(our_repo.branches) == 1
#         assert len(list(our_repo.iter_commits())) == 1
#
#     def test_shallow_clone_tag(self, tmp_path):
#         grab, config = self.prep(tmp_path, revision='my_tag', shallow=True)
#         grab.run(artefact_store=None, config=config)
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#
#     def test_shallow_clone_commit(self, tmp_path):
#         # We can't shallow grab a commit. Git won't let us.
#         grab, config = self.prep(tmp_path, revision='15c0d5', shallow=True)
#         with pytest.raises(git.GitCommandError):
#             grab.run(artefact_store=None, config=config)
#
#     # shallow update (existing folder) tests
#     def test_shallow_update_branch(self, tmp_path):
#
#         # first grab creates folder at a different commit
#         grab, config = self.prep(tmp_path, revision='main', shallow=True)
#         grab.run(artefact_store=None, config=config)
#
#         # grab again, folder already exists
#         grab, config = self.prep(tmp_path, revision='foo2', shallow=True, update=True)
#         grab.run(artefact_store=None, config=mock.Mock(source_root=tmp_path / 'source'))
#
#         assert "foo = 22" in open(grab._dst / MY_MOD).read()
#
#     def test_shallow_update_tag(self, tmp_path):
#
#         # first grab creates folder at a different commit
#         grab, config = self.prep(tmp_path, revision='main', shallow=True)
#         grab.run(artefact_store=None, config=config)
#
#         # grab again, folder already exists
#         grab, config = self.prep(tmp_path, revision='my_tag', shallow=True, update=True)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#
#     # deep clone (new folder) tests
#     def test_deep_clone_branch(self, tmp_path):
#         grab, config = self.prep(tmp_path, revision='foo2', shallow=False)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 22" in open(grab._dst / MY_MOD).read()
#
#         # check it's deep
#         our_repo = git.Repo(grab._dst)
#         assert len(our_repo.remotes['origin'].refs) == 2
#         assert len(list(our_repo.iter_commits())) == 4
#
#     def test_deep_clone_tag(self, tmp_path):
#         grab, config = self.prep(tmp_path, revision='my_tag', shallow=False)
#         grab.run(artefact_store=None, config=config)
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#
#     def test_deep_clone_commit(self, tmp_path):
#         grab, config = self.prep(tmp_path, revision='15c0d5', shallow=False)
#         grab.run(artefact_store=None, config=config)
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#
#     # deep update (existing folder) tests
#     def test_deep_update_branch(self, tmp_path):
#
#         # first grab creates folder at an old commit
#         grab, config = self.prep(tmp_path, revision='a981a2', shallow=False)
#         grab.run(artefact_store=None, config=config)
#
#         # grab again, folder already exists
#         grab, config = self.prep(tmp_path, revision='foo2', shallow=False, update=True)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 22" in open(grab._dst / MY_MOD).read()
#
#     def test_deep_update_tag(self, tmp_path):
#
#         # first grab creates folder at an old commit
#         grab, config = self.prep(tmp_path, revision='a981a2', shallow=False)
#         grab.run(artefact_store=None, config=config)
#
#         # grab again, folder already exists
#         grab, config = self.prep(tmp_path, revision='my_tag', shallow=False, update=True)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#
#     def test_deep_update_commit(self, tmp_path):
#
#         # first grab creates folder at an old commit
#         grab, config = self.prep(tmp_path, revision='a981a2', shallow=False)
#         grab.run(artefact_store=None, config=config)
#
#         # grab again, folder already exists
#         grab, config = self.prep(tmp_path, revision='15c0d5', shallow=False, update=True)
#         grab.run(artefact_store=None, config=config)
#
#         assert "foo = 2" in open(grab._dst / MY_MOD).read()
#


class TestFromGithub(object):
    # Check we can grab from github.
    # There's no need to hit their servers lots of times just for our tests,
    # so we just have one small grab here and the rest use a local repo.
    @pytest.fixture
    def url(self):
        return 'https://github.com/metomi/fab-test-data.git'

    def test_checkout_branch(self, tmp_path, url):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='main')
        checkout.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))
        assert current_branch(tmp_path / 'tiny_fortran') == 'main'

    def test_checkout_commit(self, tmp_path, url):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='ee56489')
        checkout.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))
        assert current_branch(tmp_path / 'tiny_fortran') == 'ee56489'

    def test_checkout_tag(self, tmp_path, url):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='early')
        checkout.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))
        get_tag = run_command(['git', 'describe', '--tag'], cwd=checkout._dst)
        assert get_tag.strip() == 'early'

    def test_(self, tmp_path, url):

        # run once, expect a clone, get an older commit
        clone = GitCheckout(src=url, dst='tiny_fortran', revision='early')
        clone.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))
        assert current_commit(tmp_path / 'tiny_fortran') == 'ee56489'

        # run a second time, expect a checkout, get the latest commit
        # todo: we should test getting from a second repo, too
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='main')
        checkout.run(artefact_store=None, config=mock.Mock(source_root=tmp_path))
        assert current_commit(tmp_path / 'tiny_fortran') != 'ee56489'

    # new commit
    # new branch
    # new remote


class TestFromLocalRepo(object):
    """Not hitting github"""
    pass
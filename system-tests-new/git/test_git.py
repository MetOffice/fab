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

import pytest

from fab.build_config import BuildConfig
from fab.steps.grab.git import current_commit, GitCheckout, GitMerge
from fab.tools import run_command


@pytest.fixture
def config(tmp_path):
    return BuildConfig('proj', fab_workspace=tmp_path)


class TestGitCheckout(object):
    # Check we can grab from github.
    # There's no need to hit their servers lots of times just for our tests,
    # so we just have one small grab here and the rest use a local repo.
    @pytest.fixture
    def url(self):
        return 'https://github.com/metomi/fab-test-data.git'

    def test_checkout_url(self, tmp_path, url, config):
        checkout = GitCheckout(src=url, dst='tiny_fortran')
        checkout.run(artefact_store=None, config=config)
        # todo: The commit will keep changing. Perhaps make a non-changing branch
        assert current_commit(config.source_root / 'tiny_fortran') == '3cba55e'

    def test_checkout_branch(self, tmp_path, url, config):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='main')
        checkout.run(artefact_store=None, config=config)
        # todo: The commit will keep changing. Perhaps make a non-changing branch
        assert current_commit(config.source_root / 'tiny_fortran') == '3cba55e'

    def test_checkout_tag(self, tmp_path, url, config):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='early')
        checkout.run(artefact_store=None, config=config)
        assert current_commit(config.source_root / 'tiny_fortran') == 'ee56489'

    def test_checkout_commit(self, tmp_path, url, config):
        checkout = GitCheckout(src=url, dst='tiny_fortran', revision='ee5648928893701c5dbccdbf0561c0038352a5ff')
        checkout.run(artefact_store=None, config=config)
        assert current_commit(config.source_root / 'tiny_fortran') == 'ee56489'

# todo: we could do with a test to ensure left-over files from previous fetches are cleaned away


class TestGitMerge(object):

    def test(self, tmp_path, config):

        repo_path = tmp_path / 'repo'
        repo_path.mkdir()
        run_command(['tar', '-xkf', str(Path(__file__).parent / 'tiny_fortran.tar')], cwd=repo_path)

        checkout = GitCheckout(src=repo_path / 'tiny_fortran', dst='tiny_fortran', revision=xxx)
        merge = GitMerge(src=repo_path / 'tiny_fortran', dst='tiny_fortran', revision=xxx)


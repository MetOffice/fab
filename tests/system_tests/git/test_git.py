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
import shutil
from pathlib import Path

import pytest

from fab.build_config import BuildConfig
from fab.steps.grab.git import current_commit, GitMerge


@pytest.fixture
def config(tmp_path):
    return BuildConfig('proj', fab_workspace=tmp_path)


class TestGitCheckout(object):
    # Check we can fetch from github.
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

    @pytest.fixture
    def repo_url(self, tmp_path):
        shutil.unpack_archive(Path(__file__).parent / 'repo.tar.gz', tmp_path)
        return f'file://{tmp_path}/repo'

    def test_vanilla(self, repo_url, config):

        # checkout master
        checkout_master = GitCheckout(src=repo_url, dst='tiny_fortran', revision='master')
        checkout_master.run(artefact_store=None, config=config)
        check_file = checkout_master._dst / 'file1.txt'
        assert 'This is sentence one in file one.' in open(check_file).read()

        merge_a = GitMerge(src=repo_url, dst='tiny_fortran', revision='experiment_a')
        merge_a.run(artefact_store=None, config=config)
        assert 'This is sentence one, with Experiment A modification.' in open(check_file).read()

        merge_b = GitMerge(src=repo_url, dst='tiny_fortran', revision='experiment_b')
        with pytest.raises(RuntimeError):
            merge_b.run(artefact_store=None, config=config)

        # The conflicted merge must have been aborted, check that we can do another checkout
        checkout_master.run(artefact_store=None, config=config)

# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil
from pathlib import Path
from unittest import mock

import pytest
from fab.steps.grab.fcm.merge import FcmMerge

from fab.steps.grab.fcm.checkout import FcmCheckout

from fab.steps.grab.fcm.export import FcmExport


@pytest.fixture
def repo_url(tmp_path):
    shutil.unpack_archive(
        Path(__file__).parent / 'repo.tar.gz',
        tmp_path)
    return f'file://{tmp_path}/repo'


@pytest.fixture
def config(tmp_path):
    return mock.Mock(source_root=tmp_path / 'fab_proj/source')


class TestFcmExport(object):

    def test_export(self, repo_url, config):
        step = FcmExport(src=f'{repo_url}/proj/trunk', dst='proj')
        step.run(artefact_store=None, config=config)

        # Make sure we can export twice.
        # Todo: should the export step wipe the destination first?
        step.run(artefact_store=None, config=config)


class TestFcmCheckout(object):

    def test_new_folder(self, repo_url, config):
        step = FcmCheckout(src=f'{repo_url}/proj/trunk', dst='proj')
        step.run(artefact_store=None, config=config)

        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two in file two." in file2_txt

    def test_working_copy(self, repo_url, config):

        # clean checkout of the "file 2 experiment" branch, which has different sentence from trunk in r1 and r2
        step = FcmCheckout(src=f'{repo_url}/proj/branches/file2_experiment', dst='proj', revision='7')
        step.run(artefact_store=None, config=config)

        # check we've got the revision 7 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with an experimental change." in file2_txt

        # expect an update the second time, get a newer revision and todo: check the contents
        step = FcmCheckout(src=f'{repo_url}/proj/branches/file2_experiment', dst='proj', revision='8')
        step.run(artefact_store=None, config=config)

        # check we've got the revision 8 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with a second experimental change." in file2_txt

    def test_not_working_copy(self, repo_url, config):
        # the export command just makes files, not an svn working copy
        step = FcmExport(src=f'{repo_url}/proj/trunk', dst='proj')
        step.run(artefact_store=None, config=config)

        # if we try to checkout into that folder, it should fail
        step = FcmCheckout(src=f'{repo_url}/proj/trunk', dst='proj')
        with pytest.raises(ValueError):
            step.run(artefact_store=None, config=config)


class TestFcmMerge(object):

    def test_working_copy(self, repo_url, config):
        # something to merge into; checkout trunk
        step = FcmCheckout(src=f'{repo_url}/proj/trunk', dst='proj', revision=1)
        step.run(artefact_store=None, config=config)

        # merge another branch in
        step = FcmMerge(src=f'{repo_url}/proj/branches/file2_experiment', dst='proj', revision=7)
        step.run(artefact_store=None, config=config)

        # check we've got the revision 1 text from the other branch
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with an experimental change." in file2_txt


    def test_not_working_copy(self, repo_url, config):
        pass

    def test_conflict(self, repo_url, config):
        pass

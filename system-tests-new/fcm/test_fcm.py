# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import shutil
from pathlib import Path
from unittest import mock

import pytest

from fab.steps.grab.fcm.checkout import FcmCheckout
from fab.steps.grab.fcm.export import FcmExport
from fab.steps.grab.fcm.merge import FcmMerge
from fab.tools import run_command


# TODO: We can't call fcm from the github test images.
#       Possible solution: If fcm and svn can be interchanged,
#       then we should just have one class which can be configured for either,
#       and test both variants - skipping fcm if not available.
#       Another possible solution: can we install it? :)
fcm_available = True
try:
    run_command(['fcm'])
except FileNotFoundError:
    fcm_available = False


@pytest.fixture
def repo_url(tmp_path):
    shutil.unpack_archive(
        Path(__file__).parent / 'repo.tar.gz',
        tmp_path)
    return f'file://{tmp_path}/repo'


@pytest.fixture
def config(tmp_path):
    return mock.Mock(source_root=tmp_path / 'fab_proj/source')


@pytest.mark.skipif(not fcm_available, reason="fcm command not available")
class TestFcmExport(object):

    def test_export(self, repo_url, config):
        export = FcmExport(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # Make sure we can export twice.
        # Todo: should the export step wipe the destination first?
        export.run(artefact_store=None, config=config)


@pytest.mark.skipif(not fcm_available, reason="fcm command not available")
class TestFcmCheckout(object):

    def test_new_folder(self, repo_url, config):
        checkout = FcmCheckout(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two in file two." in file2_txt

    def test_working_copy(self, repo_url, config):

        # clean checkout of the "file 2 experiment" branch, which has different sentence from trunk in r1 and r2
        checkout = FcmCheckout(
            src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision='7')
        checkout.run(artefact_store=None, config=config)

        # check we've got the revision 7 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with experimental modification." in file2_txt

        # expect an update the second time, get a newer revision and todo: check the contents
        checkout = FcmCheckout(
            src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision='8')
        checkout.run(artefact_store=None, config=config)

        # check we've got the revision 8 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with further experimental modification." in file2_txt

    def test_not_working_copy(self, repo_url, config):
        # the export command just makes files, not an svn working copy
        export = FcmExport(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # if we try to checkout into that folder, it should fail
        export = FcmCheckout(src=f'{repo_url}/proj/main/trunk', dst='proj')
        with pytest.raises(ValueError):
            export.run(artefact_store=None, config=config)

    def test_update(self, repo_url, config):
        # The scenario we're testing here is checking out across multiple builds.
        # This will usually be the same revision. The first run in a new folder will be a checkout,
        # and subsequent runs will use update, which can handle a version bump.
        f1xa = FcmCheckout(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

        f1xa = FcmCheckout(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

    def test_update_revision(self, repo_url, config):
        # Following on from test_update(), since we CAN change the revision and expect it to work, let's test that.
        f1xa = FcmCheckout(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj', revision=7)
        f1xa.run(artefact_store=None, config=config)

        f1xa = FcmCheckout(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj', revision=8)
        f1xa.run(artefact_store=None, config=config)


@pytest.mark.skipif(not fcm_available, reason="fcm command not available")
class TestFcmMerge(object):

    def test_vanilla(self, repo_url, config):
        # something to merge into; checkout trunk
        checkout = FcmCheckout(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # merge another branch in
        merge = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj')
        merge.run(artefact_store=None, config=config)

        # check we've got the revision 7 text from the other branch
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with further experimental modification." in file2_txt

    def test_revision(self, repo_url, config):
        # something to merge into; checkout trunk
        checkout = FcmCheckout(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # merge another branch in
        merge = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        merge.run(artefact_store=None, config=config)

        # check we've got the revision 7 text from the other branch
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with experimental modification." in file2_txt

    def test_not_working_copy(self, repo_url, config):
        export = FcmExport(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # try to merge into an export
        merge = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        with pytest.raises(ValueError):
            merge.run(artefact_store=None, config=config)

    def test_conflict(self, repo_url, config):
        checkout = FcmCheckout(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # this branch modifies the same line of text
        merge = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_b', dst='proj')
        with pytest.raises(RuntimeError):
            merge.run(artefact_store=None, config=config)

    def test_multiple_merges(self, repo_url, config):
        trunk = FcmCheckout(src=f'{repo_url}/proj/main/trunk', dst='proj')
        trunk.run(artefact_store=None, config=config)

        f1xa = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

        fx2 = FcmMerge(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        fx2.run(artefact_store=None, config=config)

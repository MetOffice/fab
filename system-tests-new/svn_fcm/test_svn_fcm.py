# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
"""
Test svn and fcm steps, if their underlying cli tools are available.

"""
import shutil
from pathlib import Path
from unittest import mock
import warnings

import pytest

from fab.steps.grab.fcm import FcmCheckout, FcmExport, FcmMerge
from fab.steps.grab.svn import GrabSvnBase, SvnCheckout, SvnExport, SvnMerge

# Fcm isn't available in the github test images...unless we install it from github.

# Which tools are available?
export_classes = [i for i in [SvnExport, FcmExport] if i.tool_available()]
checkout_classes = [i for i in [SvnCheckout, FcmCheckout] if i.tool_available()]
merge_classes = [i for i in [SvnMerge, FcmMerge] if i.tool_available()]
if not export_classes:
    warnings.warn('Neither svn not fcm are available for testing')


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

    # Run the test twice, once with SvnExport and once with FcmExport - depending on which tools are available.
    @pytest.mark.parametrize('export_class', export_classes)
    def test_export(self, repo_url, config, export_class):
        export = export_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # Make sure we can export twice.
        # Todo: should the export step wipe the destination first?
        export.run(artefact_store=None, config=config)


class TestFcmCheckout(object):

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_new_folder(self, repo_url, config, checkout_class):
        checkout = checkout_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two in file two." in file2_txt

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_working_copy(self, repo_url, config, checkout_class):

        # clean checkout of the "file 2 experiment" branch, which has different sentence from trunk in r1 and r2
        checkout = checkout_class(
            src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision='7')
        checkout.run(artefact_store=None, config=config)

        # check we've got the revision 7 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with experimental modification." in file2_txt

        # expect an update the second time, get a newer revision and todo: check the contents
        checkout = checkout_class(
            src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision='8')
        checkout.run(artefact_store=None, config=config)

        # check we've got the revision 8 text
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with further experimental modification." in file2_txt

    @pytest.mark.parametrize('export_class,checkout_class', zip(export_classes, checkout_classes))
    def test_not_working_copy(self, repo_url, config, export_class, checkout_class):
        # the export command just makes files, not an svn working copy
        export = export_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # if we try to checkout into that folder, it should fail
        export = checkout_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        with pytest.raises(ValueError):
            export.run(artefact_store=None, config=config)

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_update(self, repo_url, config, checkout_class):
        # The scenario we're testing here is checking out across multiple builds.
        # This will usually be the same revision. The first run in a new folder will be a checkout,
        # and subsequent runs will use update, which can handle a version bump.
        f1xa = checkout_class(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

        f1xa = checkout_class(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_update_revision(self, repo_url, config, checkout_class):
        # Following on from test_update(), since we CAN change the revision and expect it to work, let's test that.
        f1xa = checkout_class(
            src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj', revision=7)
        f1xa.run(artefact_store=None, config=config)

        f1xa = checkout_class(
            src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj', revision=8)
        f1xa.run(artefact_store=None, config=config)


class TestFcmMerge(object):

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_vanilla(self, repo_url, config, checkout_class, merge_class):
        # something to merge into; checkout trunk
        checkout = checkout_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # merge another branch in
        merge = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj')
        merge.run(artefact_store=None, config=config)

        # check we've got the revision 7 text from the other branch
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with further experimental modification." in file2_txt

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_revision(self, repo_url, config, checkout_class, merge_class):
        # something to merge into; checkout trunk
        checkout = checkout_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # merge another branch in
        merge = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        merge.run(artefact_store=None, config=config)

        # check we've got the revision 7 text from the other branch
        file2_txt = open(config.source_root / 'proj/file2.txt').read()
        assert "This is sentence two, with experimental modification." in file2_txt

    @pytest.mark.parametrize('export_class,merge_class', zip(export_classes, merge_classes))
    def test_not_working_copy(self, repo_url, config, export_class, merge_class):
        export = export_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        export.run(artefact_store=None, config=config)

        # try to merge into an export
        merge = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        with pytest.raises(ValueError):
            merge.run(artefact_store=None, config=config)

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_conflict(self, repo_url, config, checkout_class, merge_class):
        checkout = checkout_class(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        checkout.run(artefact_store=None, config=config)

        # this branch modifies the same line of text
        merge = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_b', dst='proj')
        with pytest.raises(RuntimeError):
            merge.run(artefact_store=None, config=config)

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_multiple_merges(self, repo_url, config, checkout_class, merge_class):
        trunk = checkout_class(src=f'{repo_url}/proj/main/trunk', dst='proj')
        trunk.run(artefact_store=None, config=config)

        f1xa = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a', dst='proj')
        f1xa.run(artefact_store=None, config=config)

        fx2 = merge_class(src=f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment', dst='proj', revision=7)
        fx2.run(artefact_store=None, config=config)


class TestBase(object):
    # test the base class
    def test_tool_unavailable(self):
        class Foo(GrabSvnBase):
            command = 'unlikely_cli_tool_name'

        assert not Foo.tool_available()
        with pytest.raises(RuntimeError):
            Foo('', '').run(None, config=mock.Mock(source_root=Path(__file__).parent))

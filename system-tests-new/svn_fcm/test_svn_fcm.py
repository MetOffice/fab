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

import fab
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
def config(tmp_path):
    return mock.Mock(source_root=tmp_path / 'fab_proj/source')


@pytest.fixture
def repo_url(tmp_path):
    shutil.unpack_archive(
        Path(__file__).parent / 'repo.tar.gz',
        tmp_path)
    return f'file://{tmp_path}/repo'


@pytest.fixture
def trunk(repo_url):
    # URL of the main branch.
    return f'{repo_url}/proj/main/trunk'


@pytest.fixture
def file1_experiment_a(repo_url):
    # A branch which modifies file 1.
    return f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_a'


@pytest.fixture
def file1_experiment_b(repo_url):
    # Another branch which modifies file 1. It should conflict with experiment a.
    return f'{repo_url}/proj/main/branches/dev/person_a/file1_experiment_b'


@pytest.fixture
def file2_experiment(repo_url):
    # A branch which modifies file 2.
    # It has two revisions, with different versions of the modification in r7 and r8.
    return f'{repo_url}/proj/main/branches/dev/person_b/file2_experiment'


def confirm_trunk(config) -> bool:
    file1_txt = (config.source_root / 'proj/file1.txt').read_text()
    file2_txt = (config.source_root / 'proj/file2.txt').read_text()
    if not file1_txt.startswith("This is sentence one in file one."):
        return False
    if not file2_txt.strip().endswith("This is sentence two in file two."):
        return False
    return True


def confirm_file1_experiment_a(config) -> bool:
    # Have we got the revision 7 text in file 2?
    file1_txt = (config.source_root / 'proj/file2.txt').read_text()
    return file1_txt.startswith("This is sentence one, with Experiment A modification.")


def confirm_file2_experiment_r7(config) -> bool:
    # Have we got the revision 7 text in file 2?
    file2_txt = (config.source_root / 'proj/file2.txt').read_text()
    return file2_txt.strip().endswith("This is sentence two, with experimental modification.")


def confirm_file2_experiment_r8(config) -> bool:
    # Have we got the revision 7 text in file 2?
    file2_txt = (config.source_root / 'proj/file2.txt').read_text()
    return file2_txt.strip().endswith("This is sentence two, with further experimental modification.")


class TestExport(object):

    # Run the test twice, once with SvnExport and once with FcmExport - depending on which tools are available.
    @pytest.mark.parametrize('export_class', export_classes)
    def test_export(self, file2_experiment, config, export_class):
        # Export the "file 2 experiment" branch, which has different sentence from trunk in r1 and r2
        export = export_class(src=file2_experiment, dst='proj', revision=7)
        export.run(artefact_store={}, config=config)
        assert confirm_file2_experiment_r7(config)

        # Make sure we can export twice into the same folder.
        # Todo: should the export step wipe the destination first? To remove residual, orphaned files?
        export = export_class(src=file2_experiment, dst='proj', revision=8)
        export.run(artefact_store={}, config=config)
        assert confirm_file2_experiment_r8(config)


class TestCheckout(object):

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_new_folder(self, trunk, config, checkout_class):
        checkout = checkout_class(src=trunk, dst='proj')
        checkout.run(artefact_store={}, config=config)
        assert confirm_trunk(config)

    @pytest.mark.parametrize('checkout_class', checkout_classes)
    def test_working_copy(self, file2_experiment, config, checkout_class):
        # Make sure we can checkout into a working copy.
        # The scenario we're testing here is checking out across multiple builds.
        # This will usually be the same revision. The first run in a new folder will be a checkout,
        # and subsequent runs will use update, which can handle a version bump.
        # Since we can change the revision and expect it to work, let's test that while we're here.

        with mock.patch('fab.steps.grab.svn.run_command', wraps=fab.steps.grab.svn.run_command) as wrap:

            checkout = checkout_class(src=file2_experiment, dst='proj', revision='7')
            checkout.run(artefact_store={}, config=config)
            assert confirm_file2_experiment_r7(config)
            wrap.assert_called_with([
                checkout_class.command, 'checkout', '--revision', '7',
                file2_experiment, str(config.source_root / 'proj')])

            checkout = checkout_class(src=file2_experiment, dst='proj', revision='8')
            checkout.run(artefact_store={}, config=config)
            assert confirm_file2_experiment_r8(config)
            wrap.assert_called_with(
                [checkout_class.command, 'update', '--revision', '8'],
                cwd=config.source_root / 'proj')

    @pytest.mark.parametrize('export_class,checkout_class', zip(export_classes, checkout_classes))
    def test_not_working_copy(self, trunk, config, export_class, checkout_class):
        # the export command just makes files, not a working copy
        export = export_class(src=trunk, dst='proj')
        export.run(artefact_store={}, config=config)

        # if we try to checkout into that folder, it should fail
        export = checkout_class(src=trunk, dst='proj')
        with pytest.raises(ValueError):
            export.run(artefact_store={}, config=config)


class TestMerge(object):

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_vanilla(self, trunk, file2_experiment, config, checkout_class, merge_class):
        # something to merge into; checkout trunk
        checkout = checkout_class(src=trunk, dst='proj')
        checkout.run(artefact_store={}, config=config)
        confirm_trunk(config)

        # merge another branch in
        merge = merge_class(src=file2_experiment, dst='proj')
        merge.run(artefact_store={}, config=config)
        confirm_file2_experiment_r8(config)

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_revision(self, trunk, file2_experiment, config, checkout_class, merge_class):
        # something to merge into; checkout trunk
        checkout = checkout_class(src=trunk, dst='proj')
        checkout.run(artefact_store={}, config=config)
        confirm_trunk(config)

        # merge another branch in
        merge = merge_class(src=file2_experiment, dst='proj', revision=7)
        merge.run(artefact_store={}, config=config)
        confirm_file2_experiment_r7(config)

    @pytest.mark.parametrize('export_class,merge_class', zip(export_classes, merge_classes))
    def test_not_working_copy(self, trunk, file2_experiment, config, export_class, merge_class):
        export = export_class(src=trunk, dst='proj')
        export.run(artefact_store={}, config=config)

        # try to merge into an export
        merge = merge_class(src=file2_experiment, dst='proj', revision=7)
        with pytest.raises(ValueError):
            merge.run(artefact_store={}, config=config)

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_conflict(self, file1_experiment_a, file1_experiment_b, config, checkout_class, merge_class):
        checkout = checkout_class(src=file1_experiment_a, dst='proj')
        checkout.run(artefact_store={}, config=config)
        confirm_file1_experiment_a(config)

        # this branch modifies the same line of text
        merge = merge_class(src=file1_experiment_b, dst='proj')
        with pytest.raises(RuntimeError):
            merge.run(artefact_store={}, config=config)

    @pytest.mark.parametrize('checkout_class,merge_class', zip(checkout_classes, merge_classes))
    def test_multiple_merges(self, trunk, file1_experiment_a, file2_experiment, config, checkout_class, merge_class):
        trunk = checkout_class(src=trunk, dst='proj')
        trunk.run(artefact_store={}, config=config)
        confirm_trunk(config)

        f1xa = merge_class(src=file1_experiment_a, dst='proj')
        f1xa.run(artefact_store={}, config=config)
        confirm_file1_experiment_a(config)

        fx2 = merge_class(src=file2_experiment, dst='proj', revision=7)
        fx2.run(artefact_store={}, config=config)
        confirm_file2_experiment_r7(config)


class TestBase(object):
    # test the base class
    def test_tool_unavailable(self):
        class Foo(GrabSvnBase):
            command = 'unlikely_cli_tool_name'

        assert not Foo.tool_available()
        with pytest.raises(RuntimeError):
            Foo('', '').run(None, config=mock.Mock(source_root=Path(__file__).parent))

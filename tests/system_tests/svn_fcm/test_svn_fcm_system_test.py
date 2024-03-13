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
from typing import Callable, List
from unittest import mock
import warnings

import pytest

import fab
from fab.steps.grab.fcm import fcm_checkout, fcm_export, fcm_merge
from fab.steps.grab.svn import svn_checkout, svn_export, svn_merge, tool_available

# Fcm isn't available in the github test images...unless we install it from github.

# Which tools are available?
export_funcs = []
checkout_funcs = []
merge_funcs: List[Callable] = []

if tool_available('svn'):
    export_funcs.append(svn_export)
    checkout_funcs.append(svn_checkout)
    merge_funcs.append(svn_merge)

if tool_available('fcm'):
    export_funcs.append(fcm_export)
    checkout_funcs.append(fcm_checkout)
    merge_funcs.append(fcm_merge)

if not export_funcs:
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
    @pytest.mark.parametrize('export_func', export_funcs)
    @pytest.mark.filterwarnings("ignore: Python 3.14 will, "
                                "by default, filter extracted tar archives "
                                "and reject files or modify their metadata. "
                                "Use the filter argument to control this behavior.")
    def test_export(self, file2_experiment, config, export_func):
        # Export the "file 2 experiment" branch, which has different sentence from trunk in r1 and r2
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            export_func(config, src=file2_experiment, dst_label='proj', revision=7)
            assert confirm_file2_experiment_r7(config)

        # Make sure we can export twice into the same folder.
        # Todo: should the export step wipe the destination first? To remove residual, orphaned files?
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            export_func(config, src=file2_experiment, dst_label='proj', revision=8)
            assert confirm_file2_experiment_r8(config)


@pytest.mark.filterwarnings("ignore: Python 3.14 will, "
                            "by default, filter extracted tar archives "
                            "and reject files or modify their metadata. "
                            "Use the filter argument to control this behavior.")
class TestCheckout(object):

    @pytest.mark.parametrize('checkout_func', checkout_funcs)
    def test_new_folder(self, trunk, config, checkout_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            checkout_func(config, src=trunk, dst_label='proj')
            assert confirm_trunk(config)

    @pytest.mark.parametrize('checkout_func', checkout_funcs)
    def test_working_copy(self, file2_experiment, config, checkout_func):
        # Make sure we can checkout into a working copy.
        # The scenario we're testing here is checking out across multiple builds.
        # This will usually be the same revision. The first run in a new folder will be a checkout,
        # and subsequent runs will use update, which can handle a version bump.
        # Since we can change the revision and expect it to work, let's test that while we're here.

        if checkout_func == svn_checkout:
            expect_tool = 'svn'
        elif checkout_func == fcm_checkout:
            expect_tool = 'fcm'
        else:
            assert False

        with mock.patch('fab.steps.grab.svn.run_command', wraps=fab.steps.grab.svn.run_command) as wrap, \
             pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):

            checkout_func(config, src=file2_experiment, dst_label='proj', revision='7')
            assert confirm_file2_experiment_r7(config)
            wrap.assert_called_with([
                expect_tool, 'checkout', '--revision', '7',
                file2_experiment, str(config.source_root / 'proj')])

            checkout_func(config, src=file2_experiment, dst_label='proj', revision='8')
            assert confirm_file2_experiment_r8(config)
            wrap.assert_called_with(
                [expect_tool, 'update', '--revision', '8'],
                cwd=config.source_root / 'proj')

    @pytest.mark.parametrize('export_func,checkout_func', zip(export_funcs, checkout_funcs))
    def test_not_working_copy(self, trunk, config, export_func, checkout_func):
        # the export command just makes files, not a working copy
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            export_func(config, src=trunk, dst_label='proj')

        # if we try to checkout into that folder, it should fail
        with pytest.raises(ValueError):
            checkout_func(config, src=trunk, dst_label='proj')


@pytest.mark.filterwarnings("ignore: Python 3.14 will, "
                            "by default, filter extracted tar archives "
                            "and reject files or modify their metadata. "
                            "Use the filter argument to control this behavior.")
class TestMerge(object):

    @pytest.mark.parametrize('checkout_func,merge_func', zip(checkout_funcs, merge_funcs))
    def test_vanilla(self, trunk, file2_experiment, config, checkout_func, merge_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            # something to merge into; checkout trunk
            checkout_func(config, src=trunk, dst_label='proj')
            confirm_trunk(config)

            # merge another branch in
            merge_func(config, src=file2_experiment, dst_label='proj')
            confirm_file2_experiment_r8(config)

    @pytest.mark.parametrize('checkout_func,merge_func', zip(checkout_funcs, merge_funcs))
    def test_revision(self, trunk, file2_experiment, config, checkout_func, merge_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            # something to merge into; checkout trunk
            checkout_func(config, src=trunk, dst_label='proj')
            confirm_trunk(config)

            # merge another branch in
            merge_func(config, src=file2_experiment, dst_label='proj', revision=7)
            confirm_file2_experiment_r7(config)

    @pytest.mark.parametrize('export_func,merge_func', zip(export_funcs, merge_funcs))
    def test_not_working_copy(self, trunk, file2_experiment, config, export_func, merge_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            export_func(config, src=trunk, dst_label='proj')

        # try to merge into an export
        with pytest.raises(ValueError):
            merge_func(config, src=file2_experiment, dst_label='proj', revision=7)

    @pytest.mark.parametrize('checkout_func,merge_func', zip(checkout_funcs, merge_funcs))
    def test_conflict(self, file1_experiment_a, file1_experiment_b, config, checkout_func, merge_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            checkout_func(config, src=file1_experiment_a, dst_label='proj')
            confirm_file1_experiment_a(config)

        # this branch modifies the same line of text
        with pytest.raises(RuntimeError):
            merge_func(config, src=file1_experiment_b, dst_label='proj')

    @pytest.mark.parametrize('checkout_func,merge_func', zip(checkout_funcs, merge_funcs))
    def test_multiple_merges(self, trunk, file1_experiment_a, file2_experiment, config, checkout_func, merge_func):
        with pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            checkout_func(config, src=trunk, dst_label='proj')
            confirm_trunk(config)

            merge_func(config, src=file1_experiment_a, dst_label='proj')
            confirm_file1_experiment_a(config)

            merge_func(config, src=file2_experiment, dst_label='proj', revision=7)
            confirm_file2_experiment_r7(config)

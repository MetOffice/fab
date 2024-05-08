##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

from unittest import mock

import pytest

from fab.newtools import (Categories, Fcm, Git, Subversion, Versioning)


def test_versioning_constructor():
    '''Test the versioning constructor.'''
    versioning = Versioning("versioning", "versioning.exe",
                            "working_copy_command", Categories.GIT)
    assert versioning.category == Categories.GIT
    assert versioning.name == "versioning"
    assert versioning.flags == []
    assert versioning.exec_name == "versioning.exe"
    assert versioning._working_copy_command == "working_copy_command"


def test_git_constructor():
    '''Test the git constructor.'''
    git = Git()
    assert git.category == Categories.GIT
    assert git.flags == []


def test_git_check_available():
    '''Check if check_available works as expected.
    '''
    git = Git()
    with mock.patch.object(git, "run", return_value=0):
        assert git.check_available()

    # Now test if run raises an error
    with mock.patch.object(git, "run", side_effect=RuntimeError("")):
        assert not git.check_available()


def test_git_current_commit():
    '''Check current_commit functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        assert "abc" == git.current_commit()

    run.assert_called_once_with(['log', '--oneline', '-n', '1'], cwd=".")

    # Test if we specify a path
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        assert "abc" == git.current_commit("/not-exist")

    run.assert_called_once_with(['log', '--oneline', '-n', '1'],
                                cwd="/not-exist")


def test_git_is_working_copy():
    '''Check is_working_copy functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        assert git.is_working_copy("/dst")
    run.assert_called_once_with(['status'], cwd="/dst", capture_output=False)

    with mock.patch.object(git, "run", side_effect=RuntimeError()) as run:
        assert git.is_working_copy("/dst") is False


def test_git_fetch():
    '''Check getch functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        git.fetch("/src", "/dst", revision="revision")
    run.assert_called_once_with(['fetch', "/src", "revision"], cwd="/dst",
                                capture_output=False)

    with mock.patch.object(git, "run", side_effect=RuntimeError("ERR")) as run:
        with pytest.raises(RuntimeError) as err:
            git.fetch("/src", "/dst", revision="revision")
        assert "ERR" in str(err.value)
    run.assert_called_once_with(['fetch', "/src", "revision"], cwd="/dst",
                                capture_output=False)


def test_git_checkout():
    '''Check checkout functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        git.checkout("/src", "/dst", revision="revision")
    run.assert_any_call(['fetch', "/src", "revision"], cwd="/dst",
                        capture_output=False)
    run.assert_called_with(['checkout', "FETCH_HEAD"], cwd="/dst",
                           capture_output=False)

    with mock.patch.object(git, "run", side_effect=RuntimeError("ERR")) as run:
        with pytest.raises(RuntimeError) as err:
            git.checkout("/src", "/dst", revision="revision")
        assert "ERR" in str(err.value)
    run.assert_called_with(['fetch', "/src", "revision"], cwd="/dst",
                           capture_output=False)


def test_git_merge():
    '''Check merge functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    with mock.patch.object(git, "run", return_value="abc\ndef") as run:
        git.merge("/dst", revision="revision")
    run.assert_called_once_with(['merge', "FETCH_HEAD"], cwd="/dst",
                                capture_output=False)

    # Test the behaviour if merge fails, but merge --abort works:
    # Simple function that raises an exception only the first time
    # it is called.
    def raise_1st_time():
        yield RuntimeError
        yield 0

    with mock.patch.object(git, "run", side_effect=raise_1st_time()) as run:
        with pytest.raises(RuntimeError) as err:
            git.merge("/dst", revision="revision")
        assert "Error merging revision. Merge aborted." in str(err.value)
    run.assert_any_call(['merge', "FETCH_HEAD"], cwd="/dst",
                        capture_output=False)
    run.assert_any_call(['merge', "--abort"], cwd="/dst",
                        capture_output=False)

    # Test behaviour if both merge and merge --abort fail
    with mock.patch.object(git, "run", side_effect=RuntimeError("ERR")) as run:
        with pytest.raises(RuntimeError) as err:
            git.merge("/dst", revision="revision")
        assert "ERR" in str(err.value)
    run.assert_called_with(['merge', "--abort"], cwd="/dst",
                           capture_output=False)


# ============================================================================
def test_svn_constructor():
    '''Test the git constructor.'''
    svn = Subversion()
    assert svn.category == Categories.SUBVERSION
    assert svn.flags == []
    assert svn.name == "subversion"
    assert svn.exec_name == "svn"


def test_svn_is_working_copy():
    '''Check is_working_copy functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    svn = Subversion()
    with mock.patch.object(svn, "run") as run:
        assert svn.is_working_copy("/dst")
    run.assert_called_once_with(['info'], cwd="/dst", capture_output=False)

    with mock.patch.object(svn, "run", side_effect=RuntimeError()) as run:
        assert svn.is_working_copy("/dst") is False


def test_svn_export():
    '''Check export svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    with mock.patch("fab.newtools.tool.Tool.run") as run:
        svn.export("/src", "/dst", revision="123")

    run.assert_called_once_with(["export", "--force", "--revision", "123",
                                "/src", "/dst"], env=None, cwd=None,
                                capture_output=True)

    # Test if we don't specify a revision
    with mock.patch("fab.newtools.tool.Tool.run") as run:
        svn.export("/src", "/dst")
    run.assert_called_once_with(["export", "--force", "/src", "/dst"],
                                env=None, cwd=None, capture_output=True)


def test_svn_checkout():
    '''Check checkout svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    with mock.patch("fab.newtools.tool.Tool.run", return_value="") as run:
        svn.checkout("/src", "/dst", revision="123")

    run.assert_called_once_with(["checkout", "--revision", "123",
                                "/src", "/dst"], env=None, cwd=None,
                                capture_output=True)

    # Test if we don't specify a revision
    with mock.patch("fab.newtools.tool.Tool.run",
                    return_value="abc\ndef") as run:
        svn.checkout("/src", "/dst")
    run.assert_called_once_with(["checkout", "/src", "/dst"],
                                env=None, cwd=None, capture_output=True)


def test_svn_update():
    '''Check update svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    with mock.patch("fab.newtools.tool.Tool.run") as run:
        svn.update("/dst", revision="123")

    run.assert_called_once_with(["update", "--revision", "123"],
                                env=None, cwd="/dst", capture_output=True)


def test_svn_merge():
    '''Check merge svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    with mock.patch("fab.newtools.tool.Tool.run") as run:
        svn.merge("/src", "/dst", "123")

    run.assert_called_once_with(["merge", "--non-interactive", "/src@123"],
                                env=None, cwd="/dst", capture_output=True)


# ============================================================================
def test_fcm_constructor():
    '''Test the fcb constructor.'''
    fcm = Fcm()
    assert fcm.category == Categories.FCM
    assert fcm.flags == []
    assert fcm.name == "fcm"
    assert fcm.exec_name == "fcm"

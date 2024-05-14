##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

from unittest import mock

import pytest

from fab.tools import Categories, Fcm, Git, Subversion, Versioning


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
    # Note that only the first line will be returned, and stdout of the
    # subprocess run method must be encoded (i.e. decode is called later)
    mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert "abc" == git.current_commit()

    tool_run.assert_called_once_with(
        ['git', 'log', '--oneline', '-n', '1'], capture_output=True,
        env=None, cwd='.', check=False)

    # Test if we specify a path
    mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert "abc" == git.current_commit("/not-exist")

    tool_run.assert_called_once_with(
        ['git', 'log', '--oneline', '-n', '1'], capture_output=True,
        env=None, cwd="/not-exist", check=False)


def test_git_is_working_copy():
    '''Check is_working_copy functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert git.is_working_copy("/dst")
    tool_run.assert_called_once_with(
        ['git', 'status'], capture_output=False, env=None, cwd='/dst',
        check=False)

    with mock.patch.object(git, "run", side_effect=RuntimeError()):
        assert git.is_working_copy("/dst") is False


def test_git_init():
    '''Check init functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        git.init("/src")
    tool_run.assert_called_once_with(
        ['git', 'init', '.'], capture_output=True, env=None,
        cwd='/src', check=False)


def test_git_clean():
    '''Check clean functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        git.clean('/src')
    tool_run.assert_called_once_with(
        ['git', 'clean', '-f'], capture_output=True, env=None,
        cwd='/src', check=False)


def test_git_fetch():
    '''Check getch functionality. The tests here will actually
    mock the git results, so they will work even if git is not installed.
    The system_tests will test an actual check out etc. '''

    git = Git()
    # Note that only the first line will be returned
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        git.fetch("/src", "/dst", revision="revision")
    tool_run.assert_called_once_with(
        ['git', 'fetch', "/src", "revision"], capture_output=False, env=None,
        cwd='/dst', check=False)

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

    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        git.checkout("/src", "/dst", revision="revision")
    tool_run.assert_any_call(['git', 'fetch', "/src", "revision"], cwd='/dst',
                             capture_output=False, env=None, check=False)
    tool_run.assert_called_with(['git', 'checkout', "FETCH_HEAD"], cwd="/dst",
                                capture_output=False, env=None, check=False)

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
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        git.merge("/dst", revision="revision")
    tool_run.assert_called_once_with(
        ['git', 'merge', 'FETCH_HEAD'], capture_output=False,
        env=None, cwd='/dst', check=False)

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
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert svn.is_working_copy("/dst")
    tool_run.assert_called_once_with(
        ['svn', 'info'], capture_output=False, env=None, cwd='/dst',
        check=False)

    with mock.patch.object(svn, "run", side_effect=RuntimeError()):
        assert svn.is_working_copy("/dst") is False


def test_svn_export():
    '''Check export svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.export("/src", "/dst", revision="123")

    tool_run.assert_called_once_with(
        ["svn", "export", "--force", "--revision", "123", "/src", "/dst"],
        env=None, cwd=None, capture_output=True, check=False)

    # Test if we don't specify a revision
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.export("/src", "/dst")
    tool_run.assert_called_once_with(
        ["svn", "export", "--force", "/src", "/dst"],
        env=None, cwd=None, capture_output=True, check=False)


def test_svn_checkout():
    '''Check checkout svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.checkout("/src", "/dst", revision="123")

    tool_run.assert_called_once_with(
        ["svn", "checkout", "--revision", "123", "/src", "/dst"],
        env=None, cwd=None, capture_output=True, check=False)

    # Test if we don't specify a revision
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.checkout("/src", "/dst")
    tool_run.assert_called_once_with(
        ["svn", "checkout", "/src", "/dst"],
        env=None, cwd=None, capture_output=True, check=False)


def test_svn_update():
    '''Check update svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.update("/dst", revision="123")

    tool_run.assert_called_once_with(
        ["svn", "update", "--revision", "123"],
        env=None, cwd="/dst", capture_output=True, check=False)


def test_svn_merge():
    '''Check merge svn functionality. The tests here will actually
    mock the git results, so they will work even if subversion is not
    installed. The system_tests will test an actual check out etc. '''

    svn = Subversion()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        svn.merge("/src", "/dst", "123")

    tool_run.assert_called_once_with(
        ["svn", "merge", "--non-interactive", "/src@123"],
        env=None, cwd="/dst", capture_output=True, check=False)


# ============================================================================
def test_fcm_constructor():
    '''Test the fcb constructor.'''
    fcm = Fcm()
    assert fcm.category == Categories.FCM
    assert fcm.flags == []
    assert fcm.name == "fcm"
    assert fcm.exec_name == "fcm"

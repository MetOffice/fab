##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the rsync implementation.
'''

from unittest import mock

from fab.tools import (Categories, Rsync)


def test_ar_constructor():
    '''Test the rsync constructor.'''
    rsync = Rsync()
    assert rsync.category == Categories.RSYNC
    assert rsync.name == "rsync"
    assert rsync.exec_name == "rsync"
    assert rsync.flags == []


def test_rsync_check_available():
    '''Tests the is_available functionality.'''
    rsync = Rsync()
    with mock.patch("fab.tools.tool.Tool.run") as tool_run:
        assert rsync.check_available()
    tool_run.assert_called_once_with("--version")

    # Test behaviour if a runtime error happens:
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        assert not rsync.check_available()


def test_rsync_create():
    '''Test executing an rsync, and also make sure that src always
    end on a '/'.
    '''
    rsync = Rsync()

    # Test 1: src with /
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        rsync.execute(src="/src/", dst="/dst")
    tool_run.assert_called_with(
        ['rsync', '--times', '--links', '--stats', '-ru', '/src/', '/dst'],
        capture_output=True, env=None, cwd=None, check=False)

    # Test 2: src without /
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        rsync.execute(src="/src", dst="/dst")
    tool_run.assert_called_with(
        ['rsync', '--times', '--links', '--stats', '-ru', '/src/', '/dst'],
        capture_output=True, env=None, cwd=None, check=False)

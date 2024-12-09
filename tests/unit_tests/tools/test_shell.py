##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the shell implementation.
'''

from unittest import mock

from fab.tools import Category, Shell


def test_shell_constructor():
    '''Test the Shell constructor.'''
    bash = Shell("bash")
    assert bash.category == Category.SHELL
    assert bash.name == "bash"
    assert bash.exec_name == "bash"


def test_shell_check_available():
    '''Tests the is_available functionality.'''
    bash = Shell("bash")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert bash.check_available()
    tool_run.assert_called_once_with(
        ["bash", "-c", "echo hello"], capture_output=True, env=None,
        cwd=None, check=False)

    # Test behaviour if a runtime error happens:
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        assert not bash.check_available()


def test_shell_exec_single_arg():
    '''Test running a shell script without additional parameters.'''
    ksh = Shell("ksh")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        ksh.exec("echo")
    tool_run.assert_called_with(['ksh', '-c', 'echo'],
                                capture_output=True, env=None, cwd=None,
                                check=False)


def test_shell_exec_multiple_args():
    '''Test running a shell script with parameters.'''
    ksh = Shell("ksh")
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        ksh.exec(["some", "shell", "function"])
    tool_run.assert_called_with(['ksh', '-c', 'some', 'shell', 'function'],
                                capture_output=True, env=None, cwd=None,
                                check=False)

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the PSyclone implementation.
'''

from unittest import mock

from fab.tools import (Categories, Psyclone)


def test_psyclone_constructor():
    '''Test the PSyclone constructor.'''
    psyclone = Psyclone()
    assert psyclone.category == Categories.PSYCLONE
    assert psyclone.name == "psyclone"
    assert psyclone.exec_name == "psyclone"
    assert psyclone.flags == []


def test_psyclone_check_available():
    '''Tests the is_available functionality.'''
    psyclone = Psyclone()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert psyclone.check_available()
    tool_run.assert_called_once_with(
        ["psyclone", "--version"], capture_output=True, env=None,
        cwd=None, check=False)

    # Test behaviour if a runtime error happens:
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        assert not psyclone.check_available()


def test_psyclone_process():
    '''Test running PSyclone.'''
    psyclone = Psyclone()
    mock_result = mock.Mock(returncode=0)
    # Create a mock function that returns a 'transformation script'
    # called `script_called`:
    transformation_function = mock.Mock(return_value="script_called")
    config = mock.Mock()
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        psyclone.process(config=config,
                         api="dynamo0.3",
                         x90_file="x90_file",
                         psy_file="psy_file",
                         alg_file="alg_file",
                         transformation_script=transformation_function,
                         kernel_roots=["root1", "root2"],
                         additional_parameters=["-c", "psyclone.cfg"])
    tool_run.assert_called_with(
        ['psyclone', '-api', 'dynamo0.3', '-l', 'all', '-opsy', 'psy_file',
         '-oalg', 'alg_file', '-s', 'script_called', '-c',
         'psyclone.cfg', '-d', 'root1', '-d', 'root2', 'x90_file'],
        capture_output=True, env=None, cwd=None, check=False)

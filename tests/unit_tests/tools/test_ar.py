##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the ar implementation.
'''

from pathlib import Path
from unittest import mock

from fab.tools import Categories, Ar


def test_ar_constructor():
    '''Test the ar constructor.'''
    ar = Ar()
    assert ar.category == Categories.AR
    assert ar.name == "ar"
    assert ar.exec_name == "ar"
    assert ar.flags == []


def test_ar_check_available():
    '''Tests the is_available functionality.'''
    ar = Ar()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        assert ar.check_available()
    tool_run.assert_called_once_with(
        ["ar", "--version"], capture_output=True, env=None,
        cwd=None, check=False)

    # Test behaviour if a runtime error happens:
    with mock.patch("fab.tools.tool.Tool.run",
                    side_effect=RuntimeError("")) as tool_run:
        assert not ar.check_available()


def test_ar_create():
    '''Test creating an archive.'''
    ar = Ar()
    mock_result = mock.Mock(returncode=0)
    with mock.patch('fab.tools.tool.subprocess.run',
                    return_value=mock_result) as tool_run:
        ar.create(Path("out.a"), [Path("a.o"), "b.o"])
    tool_run.assert_called_with(['ar', 'cr', 'out.a', 'a.o', 'b.o'],
                                capture_output=True, env=None, cwd=None,
                                check=False)

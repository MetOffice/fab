##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests RSync file tree synchronisation tool.
"""
from pathlib import Path

from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import call_list, not_found_callback

from fab.tools.category import Category
from fab.tools.rsync import Rsync


def test_constructor():
    """
    Tests default constructor
    """
    rsync = Rsync()
    assert rsync.category == Category.RSYNC
    assert rsync.name == "rsync"
    assert rsync.exec_name == "rsync"


def test_check_available(fake_process: FakeProcess) -> None:
    """
    Tests availability checking functionality.
    """
    fake_process.register(['rsync', '--version'], stdout='1.2.3')
    fake_process.register(['rsync', '--version'], callback=not_found_callback)

    rsync = Rsync()
    assert rsync.check_available()

    # Test behaviour if a runtime error happens:
    assert not rsync.check_available()

    assert call_list(fake_process) == [
        ['rsync', '--version'],
        ['rsync', '--version']
    ]


def test_rsync_create(fake_process: FakeProcess,
                      change_into_tmpdir: Path) -> None:
    """
    Tests performing a sync. Ensure source always ends with a '/'.
    """
    tmp_dir = change_into_tmpdir
    # Create a directory"
    directory = tmp_dir / "directory"
    directory.mkdir()
    file = tmp_dir / "file"
    file.write_text("A file\n")

    rsync = Rsync()

    # Test 1: Directory must have a '/' at the end:
    dir_command = ['rsync', '--times', '--links', '--stats', '-ru',
                   f'{directory}/', '/dst']
    fake_process.register(dir_command)
    rsync.execute(src=directory, dst=Path("/dst"))

    # Test 2: a file should not have a '/' at the end. First ensure
    # that file does indeed not have a '/' at the end (Path should discard
    # trailing / ... but just in case:)
    assert str(file)[-1] != "/"
    file_command = ['rsync', '--times', '--links', '--stats', '-ru',
                    f'{file}', '/dst']
    fake_process.register(file_command)

    rsync.execute(src=file, dst=Path("/dst"))

    assert call_list(fake_process) == [
        dir_command, file_command
    ]

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests 'ar' archiver tool.
"""
from pathlib import Path

from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import ExtendedRecorder, call_list

from fab.tools import Category, Ar


def test_constructor() -> None:
    """
    Tests default constructor.
    """
    ar = Ar()
    assert ar.category == Category.AR
    assert ar.name == "ar"
    assert ar.exec_name == "ar"
    assert ar.get_flags() == []


def test_check_available(subproc_record: ExtendedRecorder) -> None:
    """
    Tests availability functionality.
    """
    ar = Ar()
    assert ar.check_available()
    assert subproc_record.invocations() == [["ar", "--version"]]
    assert subproc_record.extras() == [{'cwd': None,
                                        'env': None,
                                        'stdout': None,
                                        'stderr': None}]


def test_check_unavailable(fake_process: FakeProcess) -> None:
    """
    Tests availability failure.
    """
    fake_process.register(['ar', '--version'],
                          returncode=1,
                          stderr="Something went wrong.")
    ar = Ar()
    assert not ar.check_available()
    assert call_list(fake_process) == [["ar", "--version"]]


def test_ar_create(subproc_record: ExtendedRecorder) -> None:
    """
    Tests creation of a new archive file.
    """
    ar = Ar()
    ar.create(Path("out.a"), [Path("a.o"), "b.o"])
    assert subproc_record.invocations() \
           == [['ar', 'cr', 'out.a', 'a.o', 'b.o']]
    assert subproc_record.extras() == [{'cwd': None,
                                        'env': None,
                                        'stderr': None,
                                        'stdout': None}]

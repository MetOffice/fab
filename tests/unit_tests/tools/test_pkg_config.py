##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests the pkg-config wrapper.
"""

from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import call_list

from fab.tools.category import Category
from fab.tools.pkg_config import PkgConfig


def test_constructor() -> None:
    """
    Tests default constructor.
    """
    pcf = PkgConfig('dummy')
    assert pcf.category == Category.MISC
    assert pcf.name == 'pkg-config(dummy)'
    assert pcf.exec_name == 'pkg-config'
    assert pcf.get_flags() == []


def test_pkg_config_check_available(fake_process: FakeProcess) -> None:
    """
    Tests availability functionality.
    """
    fake_process.register(['pkg-config', '--version'],
                          returncode=0,
                          stdout='netCDF-Fortran 4.6.1')

    pcf = PkgConfig('dummy')
    assert pcf.check_available()
    assert call_list(fake_process) == [['pkg-config', '--version']]


def test_pkg_config_check_unavailable(fake_process: FakeProcess) -> None:
    """
    Tests availability failure.
    """
    fake_process.register(['pkg-config', '--version'],
                          returncode=127,
                          stderr="command 'pkg-config' not found")
    pcf = PkgConfig("dummy")
    assert not pcf.check_available()
    assert call_list(fake_process) == [['pkg-config', '--version']]


def test_pkg_config_compiler_flags(fake_process: FakeProcess) -> None:
    """
    Tests getting the compiler flags.
    """
    fake_process.register(['pkg-config', 'dummy', '--cflags'],
                          returncode=0,
                          stdout='-I /somewhere')
    pcf = PkgConfig('dummy')
    assert pcf.get_compiler_flags() == ['-I', '/somewhere']
    assert call_list(fake_process) == [['pkg-config', 'dummy', '--cflags']]


def test_pkg_config_linker_flags(fake_process: FakeProcess) -> None:
    """
    Tests availability failure.
    """
    fake_process.register(['pkg-config', 'dummy', '--libs'],
                          returncode=0,
                          stdout='-L /somewhere -lsomewhat')
    pcf = PkgConfig('dummy')
    assert pcf.get_linker_flags() == ['-L', '/somewhere', '-lsomewhat']
    assert call_list(fake_process) == [['pkg-config', 'dummy', '--libs']]

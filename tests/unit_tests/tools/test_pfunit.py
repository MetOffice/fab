##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests 'pfunit' tool.
"""

import logging
from pathlib import Path

from pytest_subprocess.fake_process import FakeProcess


from fab.tools.category import Category
from fab.tools.pfunit import PfUnit

from tests.conftest import ExtendedRecorder, call_list


def test_pfunit_constructor_no_env(monkeypatch, caplog) -> None:
    """
    Tests constructor when $PFUNIT is not defined
    """
    # Make sure the environment variable PFUNIT is not defined:
    monkeypatch.delenv("PFUNIT", raising=False)

    with caplog.at_level(logging.ERROR):
        pfunit = PfUnit()
    assert ("$PFUNIT not defined in environment, pFUnit will likely "
            "not work." in caplog.text)
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"

    assert pfunit.category == Category.PFUNIT
    assert pfunit.name == "funitproc"
    assert pfunit.exec_name == "funitproc"


def test_pfunit_constructor_with_env(monkeypatch, caplog) -> None:
    """
    Tests constructor when $PFUNIT is defined
    """

    # Make sure the environment variable PFUNIT is defined:
    monkeypatch.setenv("PFUNIT", "/tmp")

    with caplog.at_level(logging.ERROR):
        pfunit = PfUnit()
    assert len(caplog.records) == 0
    assert pfunit.category == Category.PFUNIT
    assert pfunit.name == "funitproc"
    assert pfunit.exec_name == "funitproc"
    assert pfunit.get_root_path() == Path("/tmp")


def test_pfunit_paths(monkeypatch) -> None:
    """
    Tests root and include paths.
    """

    # Make sure the environment variable PFUNIT is defined:
    monkeypatch.setenv("PFUNIT", "/tmp")

    pfunit = PfUnit()
    assert pfunit.get_root_path() == Path("/tmp")
    assert pfunit.get_include_path() == Path("/tmp/include")


def test_pfunit_driver(monkeypatch, tmp_path: Path) -> None:
    """
    Tests that pfunit reads the driver.F90 file:
    """

    # Make sure the environment variable PFUNIT is defined:
    monkeypatch.setenv("PFUNIT", str(tmp_path))
    include_path = tmp_path / "include"
    include_path.mkdir()
    (include_path / "driver.F90").write_text("DRIVER\n")

    pfunit = PfUnit()
    assert pfunit.get_driver_f90() == "DRIVER\n"


def test_pfunit_check_available(monkeypatch,
                                subproc_record: ExtendedRecorder) -> None:
    """
    Tests availability functionality.
    """
    monkeypatch.setenv("PFUNIT", "/tmp")
    pfunit = PfUnit()
    assert pfunit.check_available()
    assert subproc_record.invocations() == [["/tmp/bin/funitproc", "-v"]]
    assert subproc_record.extras() == [{'cwd': None,
                                        'env': None,
                                        'stdout': None,
                                        'stderr': None}]


def test_pfunit_check_unavailable(monkeypatch,
                                  fake_process: FakeProcess) -> None:
    """
    Tests availability failure.
    """
    monkeypatch.setenv("PFUNIT", "/tmp")
    fake_process.register(['/tmp/bin/funitproc', '-v'],
                          returncode=1,
                          stderr="Something went wrong.")
    pfunit = PfUnit()
    assert not pfunit.check_available()
    assert call_list(fake_process) == [["/tmp/bin/funitproc", "-v"]]


def test_pfunit_process(monkeypatch,
                        tmp_path: Path,
                        subproc_record: ExtendedRecorder) -> None:
    """
    Tests processing a file
    """
    monkeypatch.setenv("PFUNIT", str(tmp_path))
    pfunit = PfUnit()
    pfunit.process(pf_path=tmp_path / "file.pf",
                   f90_out_path=tmp_path / "file.f90")

    assert subproc_record.invocations() \
           == [[str(tmp_path / "bin" / "funitproc"),
                str(tmp_path / "file.pf"),
                str(tmp_path / "file.f90")]]
    assert subproc_record.extras() == [{'cwd': None,
                                        'env': None,
                                        'stderr': None,
                                        'stdout': None}]

import os
from pathlib import Path
from tarfile import open as tar_open
from unittest.mock import Mock

from fabengine.actions.archive import METAFILE, CreateArchive, ExtractArchive
from fabengine.database import Database
from pytest import fixture, mark, raises


@fixture
def database():
    db = Mock()
    db.configuration = {}
    db.configuration["paths"] = {"work_dir": "work"}
    return db


@fixture
def tmp_archive(tmp_path: Path) -> Path:
    filename = tmp_path / "test.tar.gz"
    test = tmp_path / "test"
    test.mkdir()

    meta = test / METAFILE
    meta.touch()
    dir1 = test / "dir1"
    dir1.mkdir()
    file1 = dir1 / "file1"
    file1.touch()

    if os.system(f"cd {test} && tar zcf {filename} *") != 0:
        raise RuntimeError("unable to create tar file")

    return filename


class TestCreateArchive:
    """Unit tests for work directory archiving class."""

    @mark.parametrize("compression", ("", ".gz", ".bz2", ".xz", ".zst"))
    def test_create(self, compression: str, database: Database):
        filename = Path(f"test.tar{compression}")
        archive = CreateArchive(filename, database)
        assert archive.action_id == f"archive {filename}"

    def test_invalid(self, database: Database):
        with raises(ValueError) as exc_info:
            CreateArchive(Path("test.zip"), database)
        assert "does not have a valid suffix" in str(exc_info.value)

    def test_perform(self, database: Database, monkeypatch, tmp_path: Path):
        filename = tmp_path / "test.tar"
        check = tmp_path / "check"
        check.mkdir()
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.setitem(database.configuration["paths"], "work_dir", work)

        meta = work / METAFILE
        meta.touch()
        dir1 = work / "dir1"
        dir1.mkdir()
        file1 = dir1 / "file1"
        file1.touch()

        assert filename.exists() is False
        archive = CreateArchive(filename, database)
        archive.perform()
        assert filename.exists() is True

        with tar_open(filename, mode="r") as tarfile:
            # Archive paths are always relative
            assert tarfile.getmember("dir1") is not None
            assert tarfile.getmember("dir1/file1") is not None
            assert tarfile.getmember(METAFILE) is not None
            tarfile.extract(METAFILE, check)

        # Check metadata file has been replaced with generated data
        lines = (check / METAFILE).read_text()
        assert "timestamp:" in lines


class TestExtractArchive:
    """Test extraction of a tar file."""

    def test_create(self, database: Database):
        extract = ExtractArchive(Path("test.tar.gz"), database)
        assert extract.action_id == "extract test.tar.gz"

    def test_extract(
        self, tmp_archive: Path, database: Database, monkeypatch, tmp_path: Path
    ):
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.setitem(database.configuration["paths"], "work_dir", work)

        extract = ExtractArchive(tmp_archive, database)
        extract.perform()

        assert (work / "dir1").is_dir()
        assert (work / METAFILE).exists()

        extract = ExtractArchive(tmp_archive, database)
        extract.perform()

        assert (work / "dir1").is_dir()
        assert (work / METAFILE).exists()

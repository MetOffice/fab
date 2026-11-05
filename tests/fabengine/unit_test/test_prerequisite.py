from pathlib import Path
from unittest.mock import Mock

from fabengine.actions.archive import METAFILE
from fabengine.artefact_store import ArtefactPath, ArtefactStore
from fabengine.prerequisite import (
    AnalysedPrerequisite,
    ArtefactPrerequisite,
    BooleanPrerequisite,
    ExtractArchivePrerequisite,
    RealFilePrerequisite,
    SymbolPrerequisite,
)
from pytest import mark


class TestAnalysedPrerequisite:
    def test_function(self):
        database = Mock()
        database.prerequisites = {}
        test_unit = AnalysedPrerequisite("fred_mod", database)
        assert test_unit.ready() is False

        database.prerequisites["fred_mod"] = "present"
        assert test_unit.ready() is True


class TestSymbolPrerequisite:
    def test_function(self):
        database = Mock()
        database.symbol_table = {}
        test_unit = SymbolPrerequisite("my_symbol", database)
        assert test_unit.ready() is False

        database.symbol_table["my_symbol"] = "present"
        assert test_unit.ready() is True


class TestRealFilePrerequisite:
    def test_function(self, tmp_path: Path):
        test_file = tmp_path / "wibble.txt"
        test_unit = RealFilePrerequisite(test_file)
        assert test_unit.ready() is False

        test_file.write_text("Existing now")
        assert test_unit.ready() is True


class TestVirtualFilePrerequisite:
    def test_function(self, tmp_path: Path):
        database = Mock()
        database.artefact_store = ArtefactStore(tmp_path)
        test_unit = ArtefactPrerequisite(ArtefactPath("foo.txt"), database)
        assert test_unit.ready() is False

        # The artefact mapping is created but no file exists.
        artefact = database.artefact_store.get_artefact(ArtefactPath("foo.txt"))
        assert test_unit.ready() is False

        # Now the file exists
        artefact.real_filename.write_text("Now exisiting")
        assert test_unit.ready() is True


class TestBooleanPrerequisite:
    @mark.parametrize("value", [False, True])
    def test_function(self, value: bool):
        test_unit = BooleanPrerequisite(value)
        assert test_unit.ready() is value


class TestExtractArchivePrerequisite:
    """Test the tar archive extract prereq."""

    @mark.parametrize("value", [False, True])
    def test_function(self, value, tmp_path: Path):
        work = tmp_path / "work"
        work.mkdir()
        meta = work / METAFILE

        database = Mock()
        database.configuration = {"paths": {"work_dir": work}}
        if value:
            database.configuration["extract_path"] = "test.tar.gz"

        test_unit = ExtractArchivePrerequisite(database)
        assert test_unit.ready() is not value
        meta.touch()
        assert test_unit.ready() is True

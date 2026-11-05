from pathlib import Path

from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import (
    Database,
    PrerequisiteInfo,
    PrerequisiteType,
    SymbolInfo,
    SymbolType,
)
from fabengine.manager import FabManager
from pytest import fixture


class TestDatabase:
    @fixture
    def config(self, tmp_path: Path) -> WriteOnceDict:
        config = WriteOnceDict()
        config["paths"] = WriteOnceDict()
        config["paths"]["work_dir"] = tmp_path
        config["paths"]["build_dir"] = tmp_path / "build"
        return config

    def test_constructor(self, config: WriteOnceDict, tmp_path: Path):
        with FabManager() as manager:
            test_unit = Database(config, manager)
            assert test_unit.configuration is config
            # Check if the correct class is returned
            assert isinstance(test_unit.configuration, WriteOnceDict) is True
            # Check the configuration hasn't been altered.
            assert test_unit.configuration == {
                "paths": {"work_dir": tmp_path, "build_dir": tmp_path / "build"}
            }

    def test_tally(self, config: WriteOnceDict):
        with FabManager() as manager:
            test_unit = Database(config, manager)
            assert test_unit.processed_last_round == 0

            test_unit.bump_processed_tally()
            assert test_unit.processed_last_round == 0

            test_unit.reset_work_done()
            assert test_unit.processed_last_round == 1

            test_unit.bump_processed_tally()
            test_unit.bump_processed_tally()
            assert test_unit.processed_last_round == 1

            test_unit.reset_work_done()
            assert test_unit.processed_last_round == 2

            test_unit.reset_work_done()
            assert test_unit.processed_last_round == 0


class TestPrerequisiteInfo:
    def test_constructor(self):
        test_unit = PrerequisiteInfo("fish", PrerequisiteType.USE)
        assert test_unit.name == "fish"
        assert test_unit.nature == PrerequisiteType.USE


class TestSymbolInfo:
    def test_constructor(self):
        test_unit = SymbolInfo("teapot", SymbolType.MODULE, Path("test.f90"))
        assert test_unit.name == "teapot"
        assert test_unit.nature == SymbolType.MODULE
        assert test_unit.source_file == Path("test.f90")

from collections.abc import Generator, Iterable
from contextlib import nullcontext
from pathlib import Path
from textwrap import dedent
from typing import Any

from fabengine.actions import Action, SyntaxException, TwoPartPath
from fabengine.actions.fortran import (
    AnalyseFortran,
    AnalyseFortranTS,
    CompileFortran,
    DetermineFortranProgram,
    LinkFortran,
    PreprocessFortranBase,
    normalise_source,
)
from fabengine.artefact_store import ENCODING_META, Artefact
from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import (
    ArtefactPath,
    Database,
    PrerequisiteInfo,
    PrerequisiteType,
    SymbolInfo,
    SymbolType,
)
from fabengine.manager import FabManager
from fabengine.prerequisite import AnalysedPrerequisite, ArtefactPrerequisite
from pytest import fixture, mark, raises


@fixture(scope="function")
def database(tmp_path: Path) -> Generator[Database, None, None]:
    configuration = WriteOnceDict()
    configuration["packages"] = WriteOnceDict()
    configuration["fc_ignore_modules"] = []
    configuration["forced_prerequisites"] = {}
    configuration["fpp_definitions"] = {}
    configuration["paths"] = WriteOnceDict()
    configuration["paths"]["bin_dir"] = tmp_path / "bin"
    work_dir = tmp_path / "work"
    configuration["paths"]["work_dir"] = work_dir
    configuration["paths"]["build_dir"] = work_dir / "build"
    configuration["paths"]["module_dir"] = work_dir / "modules"
    configuration["tag_dirs"] = WriteOnceDict()
    configuration["use_open_mp"] = False
    with FabManager() as manager:
        yield Database(configuration, manager)


testcases = [
    (
        "test_prog.f90",
        False,
        ["test_prog"],
        {"test_prog": ["big_mod", "cli_mod", "special_mod"]},
        True,
    ),
    (
        "test_module.f90",
        False,
        ["test_mod"],
        {"test_mod": ["big_mod", "cli_mod", "special_mod"]},
        False,
    ),
    ("test_function.f90", False, ["test_func"], {}, False),
    ("test_subroutine.f90", False, ["test_sub"], {}, False),
    (
        "test_mod_prog.f90",
        False,
        ["edam", "example1"],
        {"edam": [], "example1": ["stilton", "gruyere"]},
        True,
    ),
    (
        "test_public_um.f90",
        False,
        ["abc", "foo", "t_bar", "t_foo", "test_foo"],
        {"foo": [], "test_foo": ["portio"]},
        True,
    ),
    (
        "test_omp.f90",
        False,
        ["test_omp"],
        {"test_omp": ["xzy"]},
        True,
    ),
    (
        "test_omp.f90",
        True,
        ["test_omp"],
        {"test_omp": ["abc", "xzy"]},
        True,
    ),
    (
        "test_anon_module.f90",
        False,
        ["anon_mod"],
        {},
        False,
    ),
    (
        "test_end_only_module.f90",
        False,
        ["anon_mod"],
        {},
        False,
    ),
]

testcase_ids = [
    "program",
    "module",
    "function",
    "subroutine",
    "module+program",
    "public+um",
    "omp pragma off",
    "omp pragma on",
    "unnamed module end",
    "module+end",
]


class TestPreprocessFortranBase:
    class PreprocessFortranStub(PreprocessFortranBase):
        def perform(self) -> Iterable[Action]:
            return []

    @mark.parametrize(
        "definitions", [{"SINGLE": "TRUE"}, {"ONE": "first", "TWO": "second"}]
    )
    def test_constructor(
        self, definitions: dict[str, str], database: Database, tmp_path: Path
    ):
        test_file = tmp_path / "piffle.F90"
        test_file.write_text(
            dedent(
                """
                ! This comment contains the degree symbol \xb0 from the
                ! ISO 8859-1 "Latin 1" character set. It will cause
                ! parsers expecting UTF-8 to fail.
                """
            )
        )

        args: list[Any] = [
            TwoPartPath(tmp_path, Path("piffle.F90")),
            "project",
            "utf8",
            database,
            definitions,
            [],
        ]
        test_unit = self.PreprocessFortranStub(*args)

        expected = "cpp -traditional-cpp -P"
        if definitions is not None:
            for key, value in definitions.items():
                expected += f" -D{key}={value}"
        assert test_unit.action_id == expected
        assert test_unit.executable == Path("cpp")
        assert test_unit.source_file == test_file
        assert test_unit.destination_file == ArtefactPath("project/piffle.f90")

    def test_destination_file(self, database: Database, tmp_path: Path):
        test_file = tmp_path / "fish.f90"
        test_file.touch()

        filename = TwoPartPath(tmp_path, Path("fish.f90"))
        test_unit = self.PreprocessFortranStub(
            filename, "test", "utf8", database, {}, []
        )
        assert test_unit.destination_file == test_unit.destination_file
        assert hash(test_unit.destination_file) == hash(test_unit.destination_file)
        assert id(test_unit.destination_file) == id(test_unit.destination_file)

    @staticmethod
    def _normalise_list(collection: Iterable[Any]) -> list[str]:
        return sorted([repr(thing) for thing in collection])


class TestNormaliseLine:
    def test_simple(self, tmp_path: Path):
        test_file = tmp_path / "test_mod.f90"
        test_file.write_text(
            dedent(
                """
                ! Copyright banner
                !
                module test_mod  ! This module
    
                end module test_mod
                """
            ).lstrip()
        )
        result = normalise_source(
            Artefact(ArtefactPath(Path("test_mod.f90")), test_file)
        )
        assert list(result) == ["module test_mod", "end module test_mod"]

    def test_continuation(self, tmp_path: Path):
        test_file = tmp_path / "test_mod.f90"
        test_file.write_text(
            dedent(
                """
                subroutine test_sub(cheese, &
                                    fish,   &
                                &   beef &
                                   )
                """
            ).lstrip()
        )
        result = normalise_source(
            Artefact(ArtefactPath(Path("test_mod.f90")), test_file)
        )
        assert list(result) == ["subroutine test_sub(cheese, fish, beef )"]


class TestAnalyseFortran:
    def test_constructor(self, database: Database):
        test_unit = AnalyseFortran(ArtefactPath("fish.f90"), database)
        assert test_unit.source == ArtefactPath("fish.f90")
        assert test_unit.prerequisites() == [
            ArtefactPrerequisite(ArtefactPath("fish.f90"), database)
        ]

    @mark.parametrize(
        "code_example, openmp, symbols, prereqs, program",
        testcases,
        ids=testcase_ids,
        indirect=["code_example"],
    )
    def test_perform(self, code_example, openmp, symbols, prereqs, program, database):
        super(WriteOnceDict, database.configuration).__setitem__("use_open_mp", openmp)

        test_unit = AnalyseFortran(code_example, database)
        actions = test_unit.perform()

        for i in symbols:
            assert i in database.symbol_table

        for name, values in prereqs.items():
            assert name in database.prerequisites
            assert len(database.prerequisites[name]) == len(values)

        if program:
            assert len(actions) == 1
            assert isinstance(actions[0], DetermineFortranProgram) is True
        else:
            assert len(actions) == 0


class TestDetermineFortranProgram:
    def test_constructor(self, database: Database):
        test_unit = DetermineFortranProgram("wibble", database)
        assert test_unit.action_id == "wibble"
        assert test_unit.prerequisites() == [AnalysedPrerequisite("wibble", database)]
        assert database.symbol_table.items() == []
        assert database.prerequisites.items() == []

    def test_perform(self, database: Database, monkeypatch):
        monkeypatch.setenv("FFLAGS", "")
        test_unit = DetermineFortranProgram("test_prog", database)

        program_path = database.configuration["paths"]["build_dir"] / "prog.f90"
        database.symbol_table["test_prog"] = SymbolInfo(
            "test_prog", SymbolType.PROGRAM, program_path
        )
        database.prerequisites["test_prog"] = [
            PrerequisiteInfo("beef_mod", PrerequisiteType.USE)
        ]
        assert test_unit.perform() == [
            CompileFortran(program_path, database.prerequisites["test_prog"], database),
            test_unit,
        ]

        beef_path = database.configuration["paths"]["build_dir"] / "beef.f90"
        database.symbol_table["beef_mod"] = SymbolInfo(
            "beef_mod", SymbolType.MODULE, beef_path
        )
        database.symbol_table["oxo_mod"] = SymbolInfo(
            "beef_mod", SymbolType.MODULE, beef_path
        )
        database.prerequisites["beef_mod"] = [
            PrerequisiteInfo("fish_mod", PrerequisiteType.USE)
        ]
        database.prerequisites["oxo_mod"] = [
            PrerequisiteInfo("fish_mod", PrerequisiteType.USE)
        ]
        assert test_unit.perform() == [
            CompileFortran(beef_path, database.prerequisites["beef_mod"], database),
            test_unit,
        ]

        # Two modules become available in the same pass...
        #
        fish_path = database.configuration["paths"]["build_dir"] / "fish.f90"
        database.symbol_table["fish_mod"] = SymbolInfo(
            "fish_mod", SymbolType.MODULE, fish_path
        )
        database.prerequisites["fish_mod"] = [
            PrerequisiteInfo("cheese_mod", PrerequisiteType.USE)
        ]

        cheese_path = database.configuration["paths"]["build_dir"] / "cheese.f90"
        database.symbol_table["cheese_mod"] = SymbolInfo(
            "cheese_mod", SymbolType.MODULE, cheese_path
        )
        database.prerequisites["cheese_mod"] = []

        assert test_unit.perform() == [
            CompileFortran(fish_path, database.prerequisites["fish_mod"], database),
            CompileFortran(cheese_path, database.prerequisites["cheese_mod"], database),
            LinkFortran(
                "test_prog",
                {"cheese_mod", "fish_mod", "beef_mod", "test_prog"},
                database,
            ),
        ]

    def test_perform_shared_source(self, database: Database, monkeypatch):
        """
        Ensures two programs which share a module only generate one compile
        task.
        """
        prog1_path = database.configuration["paths"]["build_dir"] / "prog1.f90"
        database.symbol_table["prog1"] = SymbolInfo(
            "prog1", SymbolType.PROGRAM, prog1_path
        )
        database.prerequisites["prog1"] = [
            PrerequisiteInfo("wibble_mod", PrerequisiteType.USE)
        ]

        prog2_path = database.configuration["paths"]["build_dir"] / "prog2.f90"
        database.symbol_table["prog2"] = SymbolInfo(
            "prog2", SymbolType.PROGRAM, prog2_path
        )
        database.prerequisites["prog2"] = [
            PrerequisiteInfo("wibble_mod", PrerequisiteType.USE)
        ]

        wibble_path = database.configuration["paths"]["build_dir"] / "wibble.f90"
        database.symbol_table["wibble_mod"] = SymbolInfo(
            "wibble_mod", SymbolType.MODULE, wibble_path
        )
        database.prerequisites["wibble_mod"] = [
            PrerequisiteInfo("bibble_mod", PrerequisiteType.USE)
        ]

        bibble_path = database.configuration["paths"]["build_dir"] / "bibble.f90"
        database.symbol_table["bibble_mod"] = SymbolInfo(
            "bibble_mod", SymbolType.MODULE, bibble_path
        )
        database.prerequisites["bibble_mod"] = []

        monkeypatch.setenv("FFLAGS", "")

        first_unit = DetermineFortranProgram("prog1", database)
        assert first_unit.perform() == [
            CompileFortran(
                prog1_path,
                [PrerequisiteInfo("wibble_mod", PrerequisiteType.USE)],
                database,
            ),
            CompileFortran(
                wibble_path,
                [PrerequisiteInfo("bibble_mod", PrerequisiteType.USE)],
                database,
            ),
            CompileFortran(bibble_path, [], database),
            LinkFortran("prog1", {"wibble_mod", "bibble_mod", "prog1"}, database),
        ]

        second_unit = DetermineFortranProgram("prog2", database)
        assert second_unit.perform() == [
            CompileFortran(prog2_path, database.prerequisites["prog2"], database),
            # Note: wibble_mod and bibble_mod have already been compiled at
            # this point.
            LinkFortran("prog2", {"wibble_mod", "bibble_mod", "prog2"}, database),
        ]


class TestAnalyseFortranTS:
    def test_constructor(self, database: Database):
        test_unit = AnalyseFortranTS(ArtefactPath("fish.f90"), database)
        assert test_unit.source == ArtefactPath("fish.f90")
        assert test_unit.prerequisites() == [
            ArtefactPrerequisite(ArtefactPath("fish.f90"), database)
        ]

    @mark.parametrize(
        "code_example, openmp, symbols, prereqs, program",
        testcases,
        ids=testcase_ids,
        indirect=["code_example"],
    )
    def test_perform(self, code_example, openmp, symbols, prereqs, program, database):
        super(WriteOnceDict, database.configuration).__setitem__("use_open_mp", openmp)

        test_unit = AnalyseFortranTS(code_example, database)
        actions = test_unit.perform()

        for i in symbols:
            assert i in database.symbol_table

        for name, values in prereqs.items():
            assert name in database.prerequisites
            assert len(database.prerequisites[name]) == len(values)

        if program:
            assert len(actions) == 1
            assert isinstance(actions[0], DetermineFortranProgram) is True
        else:
            assert len(actions) == 0

    @mark.parametrize(
        "code_example, syntax_checks, failure",
        [
            ("test_module.f90", False, False),
            ("test_module.f90", True, False),
            ("test_bad_syntax.f90", False, False),
            ("test_bad_syntax.f90", True, True),
        ],
        indirect=["code_example"],
        ids=[
            "valid+no checking",
            "valid+checking",
            "invalid+no checking",
            "invalid+checking",
        ],
    )
    def test_syntax_checking(
        self, code_example, syntax_checks, failure, database: Database, monkeypatch
    ):
        super(WriteOnceDict, database.configuration).__setitem__(
            "syntax_checks", syntax_checks
        )
        test_unit = AnalyseFortranTS(code_example, database)

        context = raises(SyntaxException) if failure else nullcontext(True)

        with context as result:
            test_unit.perform()

        if failure:
            assert "Syntax error parsing" in str(result.value)  # type: ignore
            assert "test_bad_syntax.f90" in str(result.value)  # type: ignore
            assert "line 3, column 3" in str(result.value)  # type: ignore
        else:
            assert result is True

    @mark.parametrize(
        "code_example, expected",
        [
            (
                "test_externals.f90",
                ("beta", "gamma", "cos", "sigma", "facet", "aspect"),
            ),
            ("test_prog.f90", ()),
        ],
        indirect=["code_example"],
        ids=["externals", "no externals"],
    )
    def test_externals(self, code_example, expected, database: Database):
        test_unit = AnalyseFortranTS(code_example, database)
        test_unit.perform()

        externals = database.prerequisites.get("externals", [])

        assert len(externals) == len(expected)

        for item in externals:
            assert item.name in expected

    @mark.parametrize(
        "code_example, encoding, failure",
        [("test_latin1.f90", "latin1", False), ("test_latin1.f90", "utf-8", True)],
        indirect=["code_example"],
        ids=["latin-1", "utf-8"],
    )
    def test_encoding(self, code_example, encoding, failure, database: Database):
        database.artefact_store.map_file(
            code_example, code_example, **{ENCODING_META: encoding}
        )

        test_unit = AnalyseFortranTS(code_example, database)

        context = raises(SystemError) if failure else nullcontext(True)

        with context as result:
            test_unit.perform()

        if failure:
            assert "UnicodeDecodeError" in str(result.value)  # type: ignore
        else:
            assert result is True
            assert "latin1" in database.symbol_table

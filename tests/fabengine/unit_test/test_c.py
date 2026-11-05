"""
Unit tests for C build actions.
Uses 1 fixture defined below:
- `fake_gcc` mocks the subprocess calls to gcc to avoid actually running compilers/linkers during tests
The rationale is that I don't want these tests to have side effects on the actual filesystem.
Nor do I need to test the compilers themselves, just that the correct commands would be generated and the correct prerequisites determined.
"""

from collections.abc import Generator
from pathlib import Path

from fabengine.actions.c import AnalyseC, CompileC, LinkC
from fabengine.artefact_store import ArtefactPath
from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import Database
from fabengine.manager import FabManager
from fabengine.prerequisite import ArtefactPrerequisite
from pytest import fixture
from pytest_subprocess.fake_process import FakeProcess

FOO_HEADER = """
    #ifndef FOO_H_
    #define FOO_H_

    int SOME_CONSTANT = 42;

    #endif // FOO_H_
"""

FOO_SOURCE = """
    #include <stdio.h>

    #include "foo.h"
    #include "bar.h"

    int main() {
        int i = SOME_CONSTANT; // This is a comment that should be ignored by AnalyseC
    //  do_a_thing(i);
        printf("Hello, from main()\n"); /* another comment
        more stuff to ignore*/    return 0;
    }
"""

BAR_HEADER = """
    #ifndef BAR_H_
    #define BAR_H_

    #include "baz.h"

    void do_a_thing(int i); /* fn definition */

    #endif // BAR_H_
"""

BAR_SOURCE = """
    #include <stdio.h>

    #include "bar.h"
    #include "baz.h"

    void do_a_thing(int i) {
    printf("Hello from do_a_thing(%d)\n", i);
    }
"""

BAZ_HEADER = """
    #ifndef BAZ_H_
    #define BAZ_H_

    static int SOME_OTHER_CONSTANT = 23;

    #endif // BAZ_H_
"""


@fixture(scope="session")
def source_dir(tmp_path_factory) -> Path:
    """
    Session-level fixture to set up a source tree.
    Runs whenever this test class is first initialised.
    """
    root = tmp_path_factory.mktemp("source")
    (root / "foo.h").write_text(FOO_HEADER)
    (root / "foo.c").write_text(FOO_SOURCE)
    (root / "bar.h").write_text(BAR_HEADER)
    (root / "bar.c").write_text(BAR_SOURCE)
    (root / "baz.h").write_text(BAZ_HEADER)
    return root


@fixture(scope="function")
def database(tmp_path: Path) -> Generator[Database, None, None]:
    """
    Sets up a per-test database with basic configuration.
    """
    configuration = WriteOnceDict()
    configuration["paths"] = WriteOnceDict()
    configuration["paths"]["bin_dir"] = tmp_path / "bin"
    configuration["paths"]["build_dir"] = tmp_path / "build"
    with FabManager() as manager:
        yield Database(configuration, manager)


@fixture(scope="function")
def fake_gcc(fake_process: FakeProcess) -> FakeProcess:
    """
    Fixture to mock subprocess calls to gcc using the "fake_process" fixture
    so that build Actions do not actually run compilers/linkers during tests.
    """
    fake_process.keep_last_process(True)
    fake_process.register(["gcc", fake_process.any()])
    return fake_process


class TestCBuild:
    def test_analyse_c(
        self, source_dir: Path, database: Database, fake_gcc: FakeProcess
    ):
        database.artefact_store.map_file(source_dir / "foo.c", ArtefactPath("foo.c"))
        test_unit = AnalyseC(ArtefactPath("foo.c"), database)
        assert test_unit.prerequisites() == [
            ArtefactPrerequisite(ArtefactPath("foo.c"), database)
        ]
        actions = test_unit.perform()
        gcc_commands = fake_gcc.calls
        assert len(gcc_commands) == 0, "AnalyseC shouldn't run any subprocess commands"
        assert len(actions) == 2, "AnalyseC should produce exactly 2 further actions"
        compile_action = next((a for a in actions if isinstance(a, CompileC)), None)
        link_action = next((a for a in actions if isinstance(a, LinkC)), None)
        assert isinstance(compile_action, CompileC)
        assert compile_action._source.name == "foo.c"
        assert isinstance(link_action, LinkC)
        assert link_action._source.name == "foo.c"
        # LinkC should depend on the corresponding object files for both #includes
        assert link_action.prerequisites() == {
            ArtefactPrerequisite(ArtefactPath("bar.o"), database),
            ArtefactPrerequisite(ArtefactPath("foo.o"), database),
        }

    def test_compile_c(self, database: Database, fake_gcc, source_dir: Path):
        TEST_COMMAND = "gcc -c foo/source/foo.c -o foo/source/foo.o"
        test_unit = CompileC(Path("foo/source/foo.c"), set(), database)
        actions = test_unit.perform()
        gcc_commands = fake_gcc.calls
        assert len(gcc_commands) == 1, (
            "CompileC should run exactly one subprocess command"
        )
        assert " ".join(gcc_commands[0]) == TEST_COMMAND
        assert len(list(actions)) == 0, (
            "CompileC should not produce any further actions"
        )

    def test_link_c(
        self, database: Database, fake_gcc, source_dir: Path, tmp_path: Path
    ):
        test_unit = LinkC(
            ArtefactPath("foo.c"),
            [
                ArtefactPrerequisite(ArtefactPath("bar.o"), database),
                ArtefactPrerequisite(ArtefactPath("foo.o"), database),
            ],
            database,
        )
        actions = test_unit.perform()
        assert len(actions) == 0, "LinkC should not produce any further actions"
        assert list(fake_gcc.calls) == [
            [
                "gcc",
                f"{tmp_path / 'build'}/bar.o",
                f"{tmp_path / 'build'}/foo.o",
                "-o",
                f"{tmp_path}/bin/foo",
            ]
        ]

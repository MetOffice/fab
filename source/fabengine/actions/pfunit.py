from __future__ import annotations

from os import environ as os_environ
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from typing import Iterable

from fabengine.actions import Action, SubprocessAction, Prerequisite, TwoPartPath
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import PreprocessFortranAction
from fabengine.database import Database


class PfUnit(SubprocessAction):
    """
    Processes pFUnit annotated source to plain source.

    This class implements the executable-per-test model where each ``.pf`` file
    gets its own driver.
    """

    def __init__(self, repo_dir: Path, source: Path, tag: str, database: Database):
        """
        :param repo_dir: Source tree root.
        :param source: ``.pf`` file relative to root.
        :param tag: Collection in workspace for generated source.
        :param database: Build system state and configuration.
        """
        self._repo_dir = repo_dir
        self._source = source
        self._tag = tag
        self._database = database

        pfunit_str = os_environ.get("PFUNIT")
        if pfunit_str is None:
            raise RuntimeError("PFUNIT must point to install directory")
        self._pfunit_path = Path(pfunit_str)
        funitproc_path = self._pfunit_path / "bin" / "funitproc"

        dest = (
            self._database.configuration.work_dir
            / self._source.with_suffix(".F90").name
        )
        arguments = ["-quiet", self._source, dest]
        super().__init__(Path(funitproc_path), arguments)

    def __str__(self) -> str:
        return "pFUnit: " + self._source.name

    _PROGRAM_PATTERN = re_compile(r"(\s*(:?end)?\s*program\s*)\w+(.*)", IGNORECASE)
    _MODULE_PATTERN = re_compile(r"(\s*(:?end)?\s*module\s*)loader(.*)", IGNORECASE)
    _USE_PATTERN = re_compile(r"(\s*use\s*)loader(.*)", IGNORECASE)
    _CALL_PATTERN = re_compile(r"", IGNORECASE)

    def _driver(
        self, template_path: Path, test_name: str, work_dir: Path
    ) -> list[Action]:
        prog_name = test_name + "_prog"
        loader_name = test_name + "_loader"
        source: list[str] = []
        for line in template_path.read_text().splitlines():
            match = self._PROGRAM_PATTERN.match(line)
            if match:
                statement = match.group(1)
                tail = match.group(3) or ""
                source.append(statement + prog_name + tail)
                continue

            match = self._MODULE_PATTERN.match(line)
            if match:
                head = match.group(1)
                tail = match.group(3) or ""
                source.append(head + loader_name + tail)
                continue

            match = self._USE_PATTERN.match(line)
            if match:
                head = match.group(1)
                tail = match.group(2) or ""
                source.append(head + loader_name + tail)
                continue

            source.append(line)

        source_file = work_dir / Path(prog_name).with_suffix(".F90")
        source_file.write_text("\n".join(source))

        include_file = work_dir / Path(prog_name).with_suffix(".inc")
        include_file.write_text(f"ADD_TEST_SUITE({test_name}_suite)\n")

        return [
            PreprocessFortranAction(
                TwoPartPath(self._repo_dir, source_file),
                self._tag,
                self._database,
                {"_TEST_SUITES": f'"{include_file.absolute()}"'},
            ),
            RunTest(self._database.configuration.work_dir / prog_name),
        ]

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    def perform(self) -> list[Action]:
        """
        Processes the test source and produces a driver for it.

        :return: Task to preprocess the resulting source. Task to process the
                 resulting driver. Task to run the test.
        """
        self.run_subprocess()
        actions: list[Action] = [
            PreprocessFortranAction(
                TwoPartPath(self._repo_dir, self._source.with_suffix(".F90")),
                self._tag,
                self._database,
            )
        ]
        actions.extend(
            self._driver(
                self._pfunit_path / "include" / "driver.F90",
                self._source.stem,
                self._database.configuration.work_dir,
            )
        )
        return actions


class RunTest(SubprocessAction):
    """
    Executes a unit test executable.
    """

    def __init__(self, executable: Path):
        """
        :param executable: Filename of executable.
        """
        self._executable = executable

        super().__init__(executable)

    def __str__(self) -> str:
        return "Execute: " + str(self._executable)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets collection of prerequisite rules.

        :return: Depends on the executable file.
        """
        return [FilePrerequisite(self._executable)]

    def perform(self) -> list[Action]:
        """
        Performs the test.

        :return: Result of running the test.
        """
        self.run_subprocess()
        return []

from __future__ import annotations

from collections.abc import Iterable
from os import environ as os_environ
from pathlib import Path
from re import IGNORECASE
from re import compile as re_compile

from fabengine.actions import Action, Prerequisite, SubprocessAction, TwoPartPath
from fabengine.actions.fortran import PreprocessFortranAction
from fabengine.cui.status import set_ps_name
from fabengine.database import Database
from fabengine.prerequisite import ExecutablePrerequisite, RealFilePrerequisite


class ImportTestData(SubprocessAction):
    """
    Copies a file tree into the workspace.
    """

    def __init__(self, source_root: Path, identifier: str, database: Database):
        """
        :param source_root: Top of the subtree to be imported.
        :param identifier: Unique name for this data.
        :param database: Build state and configuration.
        """
        self._source_root = source_root
        self._identifier = identifier
        self._database = database

        destination = (
            self._database.configuration["paths"]["work_dir"]
            / f"unit_test_{self._identifier}"
        )
        arguments = ["-a", "-delete", self._source_root, destination]
        super().__init__(Path("rsync"), arguments)

    def __str__(self) -> str:
        return f"Import test data <{self._source_root}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets action prerequisites.

        :return: Depends on source file.
        """
        return [RealFilePrerequisite(self._source_root)]

    def perform(self) -> list[Action]:
        """
        Performs action.

        :return: Empty list.
        """
        self.run_subprocess()
        self._database.unit_test_data.append(self._identifier)
        return []


class TestDataPrerequisite(Prerequisite):
    def __init__(self, identifier: str, database: Database):
        self._identifier = identifier.strip().lower()
        self._database = database

    def __str__(self) -> str:
        return f"Prerequisite test data is in place: {self._identifier}"

    def ready(self) -> bool:
        return self._identifier in self._database.unit_test_data


class PfUnit(SubprocessAction):
    """
    Processes pFUnit annotated source to plain source.

    This class implements the executable-per-test model where each ``.pf`` file
    gets its own driver.
    """

    _PARALLEL_TEST_PATTERN = re_compile(
        r"\s*@test\s*\(.*?npes\s*=\s*\[\s*(.+?)\s*].*?\)", IGNORECASE
    )

    def __init__(
        self, filename: TwoPartPath, tag: str, encoding: str, database: Database
    ):
        """
        :param filename: ``.pf`` file.
        :param tag: Collection in workspace for generated source.
        :param database: Build system state and configuration.
        """
        self._filename = filename
        self._tag = tag
        self._encoding = encoding
        self._database = database

        # Determine whether this is a parallel test and if so, how many ranks
        # it uses.
        #
        # Todo: This requires another trog through the file, representing a
        #       performance hit. In particular, it represents another filing
        #       system hit.
        #
        self._ranks = 0
        for line in self.source_file.read_text().splitlines():
            match = self._PARALLEL_TEST_PATTERN.match(line)
            if match:
                numbers = [int(number.strip()) for number in match.group(1).split(",")]
                numbers.append(self._ranks)
                self._ranks = max(numbers)

        # Todo: This is probably backwards. Shouldn't we be using the location
        #       of funitproc to intuit the location of the driver source and
        #       doing away with the need for the PFUNIT environment variable?
        #
        pfunit_str = os_environ.get("PFUNIT")
        if pfunit_str is None:
            raise RuntimeError("PFUNIT must point to pFUnit's install directory")
        self._pfunit_path = Path(pfunit_str)
        funitproc_path = self._pfunit_path / "bin" / "funitproc"

        arguments = ["-quiet", self._filename.full, self.destination_file]
        super().__init__(funitproc_path, arguments)

    def __str__(self) -> str:
        return f"pFUnit: {self._filename.branch}"

    @property
    def source_file(self) -> Path:
        return self._filename.full

    @property
    def destination_file(self) -> Path:
        artefact = self._database.artefact_store.get_artefact(
            Path(self._tag) / self._filename.branch.with_suffix(".F90")
        )
        return artefact.real_filename

    _PROGRAM_PATTERN = re_compile(r"(\s*(:?end)?\s*program\s*)\w+(.*)", IGNORECASE)
    _MODULE_PATTERN = re_compile(r"(\s*(:?end)?\s*module\s*)loader(.*)", IGNORECASE)
    _USE_PATTERN = re_compile(r"(\s*use\s*)loader(.*)", IGNORECASE)
    _CALL_PATTERN = re_compile(r"", IGNORECASE)

    def _driver(
        self, template_path: Path, test_name: str, test_dir: Path
    ) -> tuple[Path, Path]:
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

        source_file = test_dir / Path(prog_name).with_suffix(".F90")
        source_file.write_text("\n".join(source))

        include_file = test_dir / Path(prog_name).with_suffix(".inc")
        include_file.write_text(f"ADD_TEST_SUITE({test_name}_suite)\n")

        return source_file, include_file

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = [RealFilePrerequisite(self.source_file)]
        if self._tag in self._database.unit_data_copies_enqueued:
            prereqs.append(TestDataPrerequisite(self._tag, self._database))
        return prereqs

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Processes the test source and produces a driver for it.

        :return: Task to preprocess the resulting source. Task to process the
                 resulting driver. Task to run the test.
        """
        self.run_subprocess()
        real_path = TwoPartPath(
            self._database.configuration["paths"]["build_dir"].absolute() / self._tag,
            self._filename.branch.with_suffix(".F90"),
        )
        actions: list[Action] = [
            PreprocessFortranAction(
                real_path, self._tag, self._encoding, self._database, {}, []
            )
        ]
        driver_source, driver_inclusion = self._driver(
            self._pfunit_path / "include" / "driver.F90",
            self._filename.branch.stem,
            self.destination_file.parent,
        )
        actions.append(
            PreprocessFortranAction(
                TwoPartPath(
                    self._database.configuration["paths"]["build_dir"].absolute(),
                    driver_source.relative_to(
                        self._database.configuration["paths"]["build_dir"]
                    ),
                ),
                "",
                "utf-8",
                self._database,
                {"_TEST_SUITES": f'"{driver_inclusion.absolute()}"'},
                [],
            )
        )
        # Todo: We have to make an assumption as to where the executable will
        #       end up. Because there is no way for this action and the link
        #       action to talk to each other; we can't just know.
        #
        #       The shared database object could be used but this feels like
        #       an ugly solution. Maybe create the link action here and send it
        #       down the line for use later.
        #
        # Todo: It would be good to put executables next to the data directory
        #       copied previously.
        #
        test_exe = (
            self._database.configuration["paths"]["work_dir"]
            / "unit-test"
            / f"{driver_source.stem}"
        )

        # Todo: In order to avoid running a previously built executable we
        #       delete it. This will not be necessary once we have incremental
        #       builds which can detect that it is old.
        #
        if test_exe.exists():
            test_exe.unlink()

        test_dir = (
            self._database.configuration["paths"]["work_dir"] / f"unit_test_{self._tag}"
        )
        if self._tag not in self._database.unit_data_copies_enqueued:
            test_dir.mkdir(parents=True, exist_ok=True)
        if self._ranks > 0:
            actions.append(
                RunTest(
                    test_exe.absolute(),
                    self._database,
                    run_dir=test_dir,
                    ranks=self._ranks,
                )
            )
        else:  # Not parallel
            actions.append(
                RunTest(test_exe.absolute(), self._database, run_dir=test_dir)
            )

        return actions


class RunTest(SubprocessAction):
    """
    Executes a unit test executable.
    """

    def __init__(
        self,
        executable: Path,
        database: Database,
        run_dir: Path | None = None,
        ranks: int | None = None,
    ):
        """
        :param executable: Filename of executable.
        :param run_dir: Directory holding test data.
        :param ranks: Number of MPI ranks to use.
        """
        super().__init__(executable, mpi=ranks)
        self._run_dir = run_dir
        self._database = database

    def __str__(self) -> str:
        return "Execute: " + str(self._executable)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets collection of prerequisite rules.

        :return: Depends on the executable file.
        """
        return [ExecutablePrerequisite(self.executable)]

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Performs the test.

        :return: Result of running the test.
        """
        self.run_subprocess(directory=self._run_dir)
        return []

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable
from os import walk as os_walk
from pathlib import Path
from re import compile as re_compile
from urllib.parse import urlparse

from fabengine.actions import Action, Prerequisite, SubprocessAction, TwoPartPath
from fabengine.actions.c import MapC
from fabengine.actions.fortran import MapFortran, PreprocessFortranAction
from fabengine.actions.pfunit import ImportTestData, PfUnit
from fabengine.actions.psyclone import MapAlgorithm, PreprocessAlgorithm
from fabengine.actions.templaterator import Templaterator
from fabengine.artefact_store import ArtefactPath
from fabengine.cui.status import set_ps_name
from fabengine.database import Database
from fabengine.logserver import make_logger
from fabengine.prerequisite import RealFilePrerequisite
from fabengine.project import Project


class RepositoryAction(ABC):
    """
    Interface of source repositories.
    """

    def __init__(self, projects: list[Project], database: Database):
        self._projects = projects
        self._database = database

    @property
    def database(self) -> Database:
        return self._database

    @abstractmethod
    def local_copy(self) -> Path:
        """
        Gets the local copy's location.
        """
        raise NotImplementedError()

    def projects(self) -> list[Action]:
        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(
                    self.local_copy() / project.source_dir,
                    project.identifier,
                    project.source_encoding,
                    self._database,
                    project.source_include,
                )
            )
            unit_test_dir = self.local_copy() / project.unit_test_dir
            if unit_test_dir.is_dir() and self._database.configuration["testing"]:
                actions.append(
                    SourceDirectory(
                        unit_test_dir,
                        project.identifier,
                        project.source_encoding,
                        self._database,
                    )
                )
                test_data_dir = unit_test_dir / "data"
                if test_data_dir.is_dir():
                    self.database.unit_data_copies_enqueued.append(project.identifier)
                    actions.append(
                        ImportTestData(
                            test_data_dir, project.identifier, self._database
                        )
                    )
        return actions


class SourceOnDiscAction(SubprocessAction, RepositoryAction):
    """
    Source tree is on disc.
    """

    def __init__(self, remote: str, projects: list[Project], database: Database):
        """
        :param remote: Source of source in form [<hostname>:]<path>
        :param projects: Parts of the source tree to consider.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)
        self._remote = remote

        self._local = self._database.configuration["paths"]["work_dir"]
        SubprocessAction.__init__(
            self, Path("rsync"), ["-a", str(self._remote).rstrip("/"), str(self._local)]
        )

    def __str__(self) -> str:
        return "Source from disc: " + str(self._remote)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        filename = Path(self._remote.split(":")[-1])
        return self._local / filename.name

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Performs copy.

        :return: Error result if copy fails, otherwise action to examine
                 freshly imported source.
        """
        self.run_subprocess()
        return self.projects()


class SourceOnGitAction(SubprocessAction, RepositoryAction):
    """
    Source tree is held in a Git repository.
    """

    def __init__(self, url: str, projects: list[Project], database: Database):
        """
        :param url: URL for project's ``.git`` file.
        :param projects: Subtrees of concern.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)  # Parent constructor

        self._url = url

        parse_result = urlparse(self._url)
        self._scheme = parse_result.scheme
        self._netloc = parse_result.netloc
        self._path = parse_result.path

        self._revision: str | None
        self._branch: str | None
        try:
            _ = int(parse_result.fragment, 16)
            self._revision = parse_result.fragment
            self._branch = None
        except ValueError:
            self._revision = None
            self._branch = parse_result.fragment

        SubprocessAction.__init__(self, Path("git"))  # Parent constructor

    def __str__(self) -> str:
        return "Git repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        name = Path(self._path).stem
        return self.database.configuration["paths"]["work_dir"] / name

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform the extraction.

        :return: Error result if extraction fails, otherwise action to examine
                 freshly imported source.
        """
        url = f"{self._scheme}://{self._netloc}{self._path}"
        repo_marker = self.local_copy() / ".git"
        arguments: list[str | Path]

        if repo_marker.is_dir():  # Repository is present
            arguments = ["-C", self.local_copy()]
            if self._revision is None:
                arguments.append("pull")
                self.run_subprocess(additional_arguments=arguments)
                return self.projects()
        else:  # Repository is missing
            arguments = ["clone", "--depth=1"]
            if self._branch:
                arguments.append(f"--branch={self._branch}")
            arguments.extend([url, self.local_copy()])
            self.run_subprocess(additional_arguments=arguments)

        if self._revision:
            arguments = [
                "-C",
                self.local_copy(),
                "fetch",
                "--depth=1",
                "origin",
                self._revision,
            ]
            self.run_subprocess(additional_arguments=arguments)

            arguments = ["-C", self.local_copy(), "checkout", self._revision]
            self.run_subprocess(additional_arguments=arguments)

        return self.projects()


class SourceOnSubversionAction(SubprocessAction, RepositoryAction):
    def __init__(self, url: str, projects: list[Project], database: Database):
        RepositoryAction.__init__(self, projects, database)  # Parent constructor

        self._url = url
        self._database = database

        SubprocessAction.__init__(self, Path("svn"))  # Parent constructor

    def __str__(self) -> str:
        return "Subversion repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    _PATH_PATTERN = re_compile(r"(.*?)/(trunk|branches|tags)/(/*)")

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        url_parts = urlparse(self._url)
        match = self._PATH_PATTERN.match(url_parts.path)
        if match:
            path_head, _, _ = match.groups()
            _, _, project_name = path_head.rpartition("/")
        else:  # No match
            raise NotImplementedError(
                "Unable to cope with nonstandard repository layouts"
            )
        return self._database.configuration["paths"]["work_dir"] / project_name

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform the extraction.

        :return: Error result if extraction fails, otherwise action to examine
                 freshly imported source.
        """
        repo_marker = self.local_copy() / ".svn"
        arguments: list[str | Path]
        if repo_marker.is_dir():  # Repository is present
            arguments = ["update", self.local_copy()]
        else:  # Repository is missing
            parse_result = urlparse(self._url)
            url = f"{parse_result.scheme}://{parse_result.netloc}{':' + str(parse_result.port) if parse_result.port else ''}{parse_result.path}"
            arguments = ["checkout"]
            if parse_result.fragment:
                arguments.append(f"--branch={parse_result.fragment}")
            arguments.extend([url, self.local_copy()])
        self.run_subprocess(additional_arguments=arguments)
        return self.projects()


class SourceDirectory(Action):
    """
    Examines source tree for actionable files.
    """

    def __init__(
        self,
        filename: Path,
        tag: str,
        source_encoding: str,
        database: Database,
        source_include: list[Path] | None = None,
    ):
        """
        :param filename: Root of source tree.
        :param tag: Collection to use in workspace.
        :param database: Build system state and configuration.
        :param source_include: Paths to include from repository. Defaults to
                               including everything.
        """
        super().__init__(str(filename))
        self._source_dir = filename
        self._source_include = source_include or [Path(".")]
        self._source_encoding = source_encoding
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return "Source directory: " + str(self._source_dir)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: Depends on source directory.
        """
        return [RealFilePrerequisite(self._source_dir)]

    @set_ps_name
    def perform(self) -> Generator[Action, None, list[Action]]:
        """
        Performs examination.

        .. Todo:: Would it be possible to chunk output since this action can
                  generate a lot of actions. Maybe create 10 (or 100) before
                  putting ourself back on the queue. Or maybe that only seems
                  necessary for single threaded builds.

        .. Todo:: Make the actions themselves responsible for knowing how to
                  dispatch?

        .. todo:: Possibly connected to previous, can we convert the
                  if/then/else ladder into a dispatch table? This would allow
                  conditionals (such as testing) to be controlled when the
                  table was constructed rather than testing each time.

        .. todo:: Alternatively, can we use match/case structure to simplify
                  dispatch?

        :return: Action for each actionable file.
        """
        system_logger = make_logger("system")

        system_logger.info("Scanning " + str(self._source_dir))
        self._database.artefact_store.ensure_directory(Path(self._tag))

        # Todo: Tree-walk not added to pathlib until v3.12.
        #
        # for root, branches, leaves in self._source_dir.walk():
        for root_str, branches, leaves in os_walk(self._source_dir):
            root = Path(root_str)
            for leaf in leaves:
                if leaf.startswith("."):
                    continue  # Ignore "hidden" files.

                full_filename = root / leaf
                two_part_filename = TwoPartPath(
                    self._source_dir.absolute(),
                    full_filename.relative_to(self._source_dir),
                )

                # Determine whether to include the file
                #
                if not any(
                    two_part_filename.branch.is_relative_to(path)
                    for path in self._source_include
                ):
                    system_logger.debug(f"Ignoring file <{two_part_filename.branch}>")
                    continue

                actions: list[Action] = []
                if full_filename.suffix == ".f90":
                    actions.append(
                        MapFortran(
                            two_part_filename,
                            self._source_encoding,
                            self._database,
                            self._tag,
                        )
                    )
                elif full_filename.suffix == ".F90":
                    actions.append(
                        PreprocessFortranAction(
                            two_part_filename,
                            self._tag,
                            self._source_encoding,
                            database=self._database,
                            macros=self._database.configuration["fpp_definitions"],
                            force_include_dir=self._database.configuration[
                                "force_include_dir"
                            ],
                        )
                    )
                elif (
                    full_filename.suffix == ".pf"
                    and self._database.configuration["testing"]
                    and full_filename.stem
                    not in self._database.configuration["mock_tests"]
                ):
                    # Todo: The `mock_test` check is a stop gap until we have
                    #       support for mocking XIOS.
                    #
                    # Todo: No support for per-file compiler arguments. Do we
                    #       need it?
                    actions.append(
                        PfUnit(
                            two_part_filename,
                            self._tag,
                            self._source_encoding,
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".t90":
                    # Todo: Hardwired to field templating and just nasty.
                    for mapping in self._database.configuration["field_instances"]:
                        ttype = list(mapping.keys())[0]  # noqa: RUF015
                        tkind = mapping[ttype]
                        leafname = ArtefactPath(
                            full_filename.stem[:-4] + "_" + tkind + "_mod.f90"
                        )
                        inserts = {"type": ttype, "kind": tkind}
                        actions.append(
                            Templaterator(
                                full_filename,
                                leafname,
                                inserts,
                                self._database,
                            )
                        )
                elif full_filename.suffix == ".X90":
                    actions.append(
                        PreprocessAlgorithm(
                            two_part_filename,
                            self._tag,
                            self._source_encoding,
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".x90":
                    actions.append(
                        MapAlgorithm(two_part_filename, self._database, tag=self._tag)
                    )
                elif full_filename.suffix == ".c":
                    actions.append(
                        MapC(
                            two_part_filename,
                            self._database,
                            self._tag,
                        )
                    )
                else:
                    system_logger.debug("Ignoring file: " + full_filename.name)

                yield from actions
        return []

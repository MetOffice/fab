from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable
from os import walk as os_walk
from pathlib import Path
from re import compile as re_compile
from shlex import split as shsplit
from subprocess import CompletedProcess

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
from fabengine.prerequisite import ExtractArchivePrerequisite, RealFilePrerequisite
from fabengine.project import Project


class RepositoryAction(ABC):
    """
    Interface of source repositories.
    """

    def __init__(self, projects: list[Project], database: Database):
        self._projects = projects
        self._database = database

    def __hash__(self) -> int:
        return hash(str(self._projects))

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

    _REMOTE_PATTERN = re_compile(r"([\w\.]+@)?[\w\.]+:")

    def __init__(
        self,
        identity: str,
        source: str | Path,
        projects: list[Project],
        database: Database,
    ):
        """
        :param remote: Source of source in form [<hostname>:]<path>
        :param projects: Parts of the source tree to consider.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)

        self._source = source
        self._identity = identity
        self._dest = database.configuration["paths"]["work_dir"].resolve()
        self._is_remote = self._REMOTE_PATTERN.match(str(source))

        SubprocessAction.__init__(self, identification=f"Local source {identity} copy")

    def __str__(self) -> str:
        return "Source from disc: " + str(self._source)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return [ExtractArchivePrerequisite(self._database)]

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        return self._dest / self._identity

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Performs copy.

        :return: Error result if copy fails, otherwise action to examine
                 freshly imported source.
        """

        command = (
            f"rsync -a {str(self._source).removesuffix('/')}/ {self.local_copy()} "
        )

        if not self._is_remote and Path(self._source).is_relative_to(self._dest):
            command += f"--filter=- {self._dest.relative_to(self._source)} "

        self.run_subprocess(additional_arguments=shsplit(command))

        return self.projects()


class RemoteGitAction(SubprocessAction, RepositoryAction):
    """
    Source tree is a remotely held git repository, eg. on github
    """

    def __init__(
        self,
        identity: str,
        source: str,
        ref: str | None,
        projects: list[Project],
        database: Database,
    ):
        """
        :param identity: name of the repo
        :param source: url to remote source
        :param ref: git version control reference (eg. hash, tag, branch)
        :param projects: Subtrees of concern.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)

        self._identity = identity
        self._source = source
        self._ref = ref

        SubprocessAction.__init__(self, identification=f"Remote Git Extract {identity}")

    def __hash__(self) -> int:
        return hash(str(self._source))

    def __str__(self) -> str:
        return "Remote Git repository: " + self._source

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return [ExtractArchivePrerequisite(self._database)]

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        return self.database.configuration["paths"]["work_dir"] / self._identity

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform the extraction.

        :return: Error result if extraction fails, otherwise action to examine
                 freshly imported source.
        """

        repo_marker = self.local_copy() / ".git"

        if not repo_marker.is_dir():
            self.run_subprocess(
                additional_arguments=shsplit(
                    f"git clone {self._source} {self.local_copy()} --depth=1"
                )
            )

        if self._ref:
            self.run_subprocess(
                additional_arguments=shsplit(
                    f"git -C {self.local_copy()} fetch origin {self._ref} --depth=1"
                )
            )
            self.run_subprocess(
                additional_arguments=shsplit(
                    f"git -C {self.local_copy()} checkout FETCH_HEAD"
                )
            )

        return self.projects()


class LocalGitAction(SubprocessAction, RepositoryAction):
    """
    Source tree is a locally held git repository, either on this filesystem or and ssh
    accessible filesystem
    """

    def __init__(
        self,
        identity: str,
        source: str | Path,
        ref: str | None,
        projects: list[Project],
        database: Database,
    ):
        """
        :param identity: name of the repo
        :param source: local source path (optionally with hostname)
        :param ref: git version control reference (eg. hash, tag, branch)
        :param projects: Subtrees of concern.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)

        self._identity = identity
        self._source = str(source)
        self._ref = ref

        SubprocessAction.__init__(self, identification=f"Local Git Extract {identity}")

    def __hash__(self) -> int:
        return hash(str(self._source))

    def __str__(self) -> str:
        return f"Local Git repository: {self._source}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return [ExtractArchivePrerequisite(self._database)]

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        return self.database.configuration["paths"]["work_dir"] / self._identity

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform the extraction.

        :return: Error result if extraction fails, otherwise action to examine
                 freshly imported source.
        """

        try:
            host, path = self._source.split(":", 1)
        except ValueError:
            host = None
            path = self._source

        # Populate a list of paths to ignore in the rsync based on the git ignore
        # eg. Ignores command line build work/bin directories
        exclude_paths = []
        if host:
            command = f"ssh {host} "
        command += f"git -C {path} status --ignored -s"
        result: CompletedProcess = self.run_subprocess(
            additional_arguments=shsplit(command), output=True
        )  # type: ignore
        for ignore_file in result.stdout.split("\n"):
            ignore_file = ignore_file.strip()
            if not ignore_file.startswith("!!"):
                continue
            ignore_file = ignore_file.removeprefix("!!").strip()
            exclude_paths.append(ignore_file)

        # Trailing slash required for rsync - ensure we don't double up
        command = f"rsync -a {self._source.removesuffix('/')}/ {self.local_copy()}"
        for item in exclude_paths:
            command += f" --exclude '{item}'"
        self.run_subprocess(additional_arguments=shsplit(command))

        if self._ref:
            self.run_subprocess(
                additional_arguments=shsplit(
                    f"git -C {self.local_copy()} checkout {self._ref}"
                )
            )

        return self.projects()


class RemoteSVNAction(SubprocessAction, RepositoryAction):
    def __init__(
        self,
        identity: str,
        source: str,
        ref: str | None,
        projects: list[Project],
        database: Database,
    ):
        """
        :param identity: name of the repo
        :param source: url to remote source
        :param ref: git version control reference (eg. hash, tag, branch)
        :param projects: Subtrees of concern.
        :param database: Build system state and configuration.
        """

        RepositoryAction.__init__(self, projects, database)

        self._identity = identity
        self._source = source
        self._ref = ref
        self._database = database

        SubprocessAction.__init__(
            self, executable=Path("svn"), identification=f"SVN Extract {identity}"
        )

    def __str__(self) -> str:
        return "Subversion repository: " + self._source

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        return self._database.configuration["paths"]["work_dir"] / self._identity

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
            if self._ref:
                source = f"{self._source}@{self._ref}"
            else:
                source = self._source
            arguments = ["checkout", source, self.local_copy()]
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
        return [
            RealFilePrerequisite(self._source_dir),
            ExtractArchivePrerequisite(self._database),
        ]

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

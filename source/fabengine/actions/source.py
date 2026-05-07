from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from multiprocessing import get_logger as mp_get_logger
from os import walk as os_walk
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

from fabengine.actions import Action, Prerequisite, SubprocessAction, TwoPartPath
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import (
    ImportFortran,
    PreprocessFortranAction,
    ImportInclusion,
)
from fabengine.actions.pfunit import PfUnit
from fabengine.actions.psyclone import PSyclone, PreprocessAlgorithm
from fabengine.actions.templaterator import Templaterator
from fabengine.database import Database
from fabengine.project import Project


class RepositoryAction(ABC):
    """
    Interface of source repositories.
    """

    def __init__(self, projects: list[Project], database: Database):
        self._projects = projects
        self._database = database

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
                    self._database,
                    project.source_include,
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
        self._database = database

        remote = str(self._remote).rstrip("/")
        local = str(self._database.configuration.work_dir)
        SubprocessAction.__init__(self, Path("rsync"), ["-a", remote, local])

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
        return self._database.configuration.work_dir / filename.name

    def perform(self) -> list[Action]:
        """
        Performs copy.

        :return: Error result if copy fails, otherwise action to examine
                 freshly imported source.
        """
        self.run_subprocess()
        return self.projects()


class SourceOnGitHubAction(SubprocessAction, RepositoryAction):
    """
    Source tree is held by GitHub.

    Specific to GitHub, doesn't work on other Git repositories.
    """

    def __init__(self, url: str, projects: list[Project], database: Database):
        """
        :param url: Location of ``.git`` file.
        :param projects: Subtrees of concern.
        :param database: Build system state and configuration.
        """
        RepositoryAction.__init__(self, projects, database)  # Parent constructor
        _, netloc, _, _, _, _ = urlparse(url)
        if netloc.split("@")[-1].lower() != "github.com":
            raise RuntimeError("URL passed to SourceOnGitHubAction is not on GitHub")
        self._url = url
        self._database = database

        SubprocessAction.__init__(self, Path("git"))  # Parent constructor

    def __str__(self) -> str:
        return "GitHub repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: No prerequisites.
        """
        return []

    def local_copy(self) -> Path:
        """
        :return: Path of local copy.
        """
        _, netloc, path, _, query, fragment = urlparse(self._url)
        name = Path(path).stem
        return self._database.configuration.work_dir / name

    def perform(self) -> list[Action]:
        """
        Perform the extraction.

        :return: Error result if extraction fails, otherwise action to examine
                 freshly imported source.
        """
        repo_marker = self.local_copy() / ".git"
        arguments: list[str | Path]
        if repo_marker.is_dir():  # Repository is present
            arguments = ["-C", str(self.local_copy()), "pull"]
        else:  # Repository is missing
            scheme, netloc, path, _, _, fragment = urlparse(self._url)
            url = f"{scheme}://{netloc}{path}"
            arguments = ["clone", "--depth=1"]
            if fragment:
                arguments.append(f"--branch={fragment}")
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
        database: Database,
        source_include: Optional[list[Path]] = None,
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
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return "Source directory: " + str(self._source_dir)

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: Depends on source directory.
        """
        return [FilePrerequisite(self._source_dir)]

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
        mp_get_logger().info("Scanning " + str(self._source_dir))
        project_dir = self._database.configuration.build_dir / self._tag
        project_dir.mkdir(parents=True, exist_ok=True)

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
                    mp_get_logger().info(f"Ignoring file <{two_part_filename.branch}>")
                    continue

                actions: list[Action] = []
                if full_filename.suffix == ".f90":
                    actions.append(
                        ImportFortran(
                            two_part_filename,
                            self._tag,
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".F90":
                    actions.append(
                        PreprocessFortranAction(
                            two_part_filename,
                            self._tag,
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".pf":
                    # Todo: No support for per-file compiler arguments. Do we
                    #       need it?
                    actions.append(
                        PfUnit(
                            two_part_filename.root,
                            two_part_filename.branch,
                            self._tag,
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".t90":
                    # Todo: Hardwired to field templating and just nasty.
                    for mapping in self._database.configuration.field_instances:
                        ttype = list(mapping.keys())[0]
                        tkind = mapping[ttype]
                        leafname = full_filename.stem[:-4] + "_" + tkind + "_mod.f90"
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
                            self._database,
                        )
                    )
                elif full_filename.suffix == ".x90":
                    actions.append(
                        PSyclone(
                            two_part_filename,
                            self._tag,
                            self._database,
                        )
                    )
                elif (
                    full_filename.suffix
                    in self._database.configuration.inclusion_suffixes
                ):
                    actions.append(
                        ImportInclusion(
                            two_part_filename,
                            self._tag,
                            self._database,
                        )
                    )
                else:
                    mp_get_logger().info("Ignoring file: " + full_filename.name)

                for action in actions:
                    yield action
        return []

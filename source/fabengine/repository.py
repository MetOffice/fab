from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from shlex import split as shsplit
from subprocess import run

from yaml import safe_load

from fabengine.actions.source import (
    LocalGitAction,
    RemoteGitAction,
    RemoteSVNAction,
    RepositoryAction,
    SourceOnDiscAction,
)
from fabengine.database import Database
from fabengine.project import Project


class ReadDependencies:
    """
    Load in a dependencies yaml file
    """

    def __init__(self, dependencies_file: Path | None):
        """
        :param dependencies_file: Path to source file
        """

        self._dependencies_file = dependencies_file

        if not dependencies_file:
            self._dependencies = None
        else:
            with open(dependencies_file, "r") as stream:
                self._dependencies = safe_load(stream)

    @property
    def dependencies_file(self) -> Path | None:
        """
        Path to the dependencies file
        """
        return self._dependencies_file

    @property
    def dependencies(self) -> dict | None:
        """
        Dictionary of dependencies
        """
        return self._dependencies


class RepositoryException(Exception):
    pass


class Repository(ABC):
    """
    Abstract version control tool.
    """

    def __init__(
        self,
        identity: str,
        source: str | Path,
        ref: str | None = None,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param paths: Named paths in this directory.
        :param projects: Projects in this directory.
        """
        self._identity = identity
        self._source = source
        self._ref = ref
        self._paths = paths or {}
        self._projects: list[Project] = projects or []

    def add_project_directory(self, project: Project) -> None:
        """
        Adds a project to the repository.

        :param project: New project.
        """
        self._projects.append(project)

    def source_is_local(self) -> bool:
        """
        Check if the source is remote, or local to the filesystem or a filesystem
        accessible via ssh

        :return: True if local
        """
        try:
            host, source = str(self._source).split(":", 1)
            result = run(
                shsplit(f"ssh {host} test -e {source}"),
                capture_output=True,
                check=False,
            )
            # Return not, as code will be 1 if it doesn't exist
            return not bool(result.returncode)
        except ValueError:
            return Path(self._source).exists()

    @property
    def identity(self) -> str:
        """
        Source for this repo
        """
        return self._identity

    @property
    def source(self) -> str | Path:
        """
        Source for this repo
        """
        return self._source

    @property
    def ref(self) -> str | None:
        """
        Version Control reference for this repo
        """
        return self._ref

    @property
    def paths(self) -> dict[str, Path]:
        """
        Gets all special paths.
        """
        return self._paths

    @property
    def projects(self) -> list[Project]:
        """
        Gets all projects in directory.
        """
        return self._projects

    @abstractmethod
    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to extract repository.

        :param database: Build state and configuration.
        """
        raise NotImplementedError()


class FileTreeRepository(Repository):
    """
    Treat the filing system as a repository of source.
    """

    def __init__(
        self,
        identity: str,
        source: Path | str,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param filename: Location of source.
        """
        super().__init__(identity, source, None, paths, projects)

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to copy source.

        :rtype: SourceOnDiscAction
        """
        return SourceOnDiscAction(self._identity, self._source, self.projects, database)


class GitRepository(Repository):
    """
    Fetches source from a Git repository.
    """

    def __init__(
        self,
        identity: str,
        dependencies_file: Path | None = None,
        source: str | None = None,
        ref: str | None = None,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param identity: name of the repo
        :param dependencies_file: Path to dependencies file
        :param source: url to remote source
        :param ref: git version control reference (eg. hash, tag, branch)
        :param paths: Named paths in this directory.
        :param projects: Initial list of projects held in repository.
        """

        self._identity = identity
        self._dependencies = ReadDependencies(dependencies_file)
        source, ref = default_source(
            identity,
            self._dependencies,
            source,
            ref,
            self.default_git_source,
        )
        super().__init__(identity, source, ref, paths, projects)

    @staticmethod
    def default_git_source(dependencies_file: Path) -> str:
        """
        :return: root path of dependencies file clone, or nothing if not a git source
        """
        command = shsplit(
            f"git -C {dependencies_file.parent} rev-parse --show-toplevel"
        )
        return run(command, capture_output=True, text=True, check=False).stdout.strip()

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to get source.

        :return: Source extract action
        """

        if self.source_is_local():
            return LocalGitAction(
                self._identity, self._source, self._ref, self.projects, database
            )
        return RemoteGitAction(
            self._identity, str(self._source), self._ref, self.projects, database
        )


class SVNRepository(Repository):
    def __init__(
        self,
        identity: str,
        dependencies_file: Path | None = None,
        source: str | None = None,
        ref: str | None = None,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param identity: name of the repo
        :param dependencies_file: Path to dependencies file
        :param source: url to remote source
        :param ref: git version control reference (eg. hash, tag, branch)
        :param paths: Named paths in this directory.
        :param projects: Initial list of projects held in repository.
        """

        self._identity = identity
        self._dependencies = ReadDependencies(dependencies_file)
        source, ref = default_source(
            identity,
            self._dependencies,
            source,
            ref,
            self.default_svn_source,
        )
        super().__init__(identity, source, ref, paths, projects)

    @staticmethod
    def default_svn_source(dependencies_file: Path) -> str:
        """
        :return: svn wc root of dependencies file, or nothing if not svn source
        """
        command = shsplit(f"svn info --show-item wc-root {dependencies_file.parent}")
        return run(command, capture_output=True, text=True, check=False).stdout.strip()

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to get source.

        :return: Source extract action
        """

        if self.source_is_local():
            return SourceOnDiscAction(
                self._identity, self._source, self._projects, database
            )
        return RemoteSVNAction(
            self._identity, str(self._source), self._ref, self.projects, database
        )


def default_source(
    identity: str,
    dependencies_data: ReadDependencies,
    source: str | None,
    ref: str | None,
    default_func: Callable,
) -> tuple:
    """
    Populate default source and ref values for a given dependency if they're not already
    set.
    :param identity: Name of the dependency
    :param dependencies_data: dependencies read from a yaml file
    :param source: Source (url or filesystem path) to the dependency
    :param ref: Version Control reference
    :param default_func: Function to populate default value for this type of dependency
    """
    if dependencies_data.dependencies is None and source is None:
        raise RepositoryException(
            "One of the source or dependencies files must be provided."
        )
    dependencies = dependencies_data.dependencies or {}
    if identity not in dependencies and not source:
        raise RepositoryException(
            f"Repo {identity} not found in provided dependencies file."
        )
    if not source:
        source = dependencies[identity]["source"] or default_func(
            dependencies_data.dependencies_file
        )
        if not source:
            raise RepositoryException(
                f"Unable to work out the correct source for {identity}"
            )
    if not ref and identity in dependencies:
        ref = dependencies[identity]["ref"] or ""
    return source, ref

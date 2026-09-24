from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from fabengine.actions.source import (
    RepositoryAction,
    SourceOnDiscAction,
    SourceOnGitAction,
    SourceOnSubversionAction,
)
from fabengine.database import Database
from fabengine.project import Project


class Repository(ABC):
    """
    Abstract version control tool.
    """

    def __init__(
        self,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param paths: Named paths in this directory.
        :param projects: Projects in this directory.
        """
        self._paths = paths or {}
        self._projects: list[Project] = projects or []

    def add_project_directory(self, project: Project) -> None:
        """
        Adds a project to the repository.

        :param project: New project.
        """
        self._projects.append(project)

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
        filename: Path,
        paths: dict[str, Path],
        projects: list[Project],
    ):
        """
        :param filename: Location of source.
        """
        super().__init__(paths, projects)
        self._filename = filename

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to copy source.

        :rtype: SourceOnDiscAction
        """
        return SourceOnDiscAction(self._filename, self.projects, database)


class GitRepository(Repository):
    """
    Fetches source from a Git repository.
    """

    def __init__(
        self,
        url: str,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        """
        :param url: Git project URL.
                    e.g. ssh://git@example.com/Example/project.git
        :param projects: Initial list of projects held in repository.
        """
        super().__init__(paths, projects)
        self._url = url

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to get source.

        :rtype: SourceOnGitAction
        """
        return SourceOnGitAction(self._url, self.projects, database)


class GitHubRepository(GitRepository):
    """
    Fetches source for a Git repository hosted by GitHub.
    """

    def __init__(
        self,
        url: str,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        parse_result = urlparse(url)
        if parse_result.hostname != "github.com":
            raise RuntimeError(
                f"URL passed to GitHubRepository is not on GitHub: {parse_result.hostname}"
            )
        if parse_result.scheme not in ["https", "ssh"]:
            raise RuntimeError(
                f"Unsupported URL scheme in GitHubRepository: {parse_result.scheme}"
            )
        if (
            ":" in parse_result.netloc
            and not parse_result.netloc.split(":")[-1].isdigit()
        ):
            # a common mistake is to copy the SSH URI from github; this will include a colon instead of a slash
            # that _could_ represent a port number, but if it doesn't then future calls to git will fail
            raise RuntimeError("Malformed URL in SourceOnGitHubAction")

        super().__init__(url, paths, projects)


class SubversionRepository(Repository):
    def __init__(
        self,
        url: str,
        paths: dict[str, Path] | None = None,
        projects: list[Project] | None = None,
    ):
        super().__init__(paths, projects)
        self._url = url

    def create_action(self, database: Database) -> RepositoryAction:
        return SourceOnSubversionAction(self._url, self.projects, database)

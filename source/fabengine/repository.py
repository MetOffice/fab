from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fabengine.actions.source import (
    RepositoryAction,
    SourceOnDiscAction,
    SourceOnGitHubAction,
)
from fabengine.database import Database
from fabengine.project import Project


class Repository(ABC):
    """
    Abstract version control tool.
    """

    def __init__(
        self,
        paths: Optional[dict[str, Path]] = None,
        projects: Optional[list[Project]] = None,
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
        filename: str,
        paths: Optional[dict[str, Path]] = None,
        projects: Optional[list[Project]] = None,
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


class GitHubRepository(Repository):
    """
    Fetches source from Git repository associated with a GitHub project.
    """

    def __init__(
        self,
        url: str,
        paths: Optional[dict[str, Path]] = None,
        projects: Optional[list[Project]] = None,
    ):
        """
        :param url: GitHub project URL.
                    e.g. ssh://git@github.com/Example/project.git
        :param projects: Initial list of projects held in repository.
        """
        super().__init__(paths, projects)
        self._url = url

    def create_action(self, database: Database) -> RepositoryAction:
        """
        Creates an action to get source.

        :rtype: SourceOnGitHubAction
        """
        return SourceOnGitHubAction(self._url, self.projects, database)

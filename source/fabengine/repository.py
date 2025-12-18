from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fabengine.actions.source import (RepositoryAction, SourceOnDiscAction,
                                      SourceOnGitHubAction)
from fabengine.database import Database
from fabengine.project import Project


class Repository(ABC):
    def __init__(self, projects: Optional[list[Project]] = None):
        self._projects: list[Project] = projects or []

    def add_project_directory(self, project: Project) -> None:
        self._projects.append(project)

    @property
    def projects(self) -> list[Project]:
        return self._projects

    @abstractmethod
    def create_action(self, work_dir: Path, database: Database) -> RepositoryAction:
        raise NotImplementedError()


class FileTreeRepository(Repository):
    def __init__(self, filename: str, projects: Optional[list[Project]] = None):
        super().__init__(projects)
        self._filename = filename

    def create_action(self, work_dir: Path, database: Database) -> RepositoryAction:
        return SourceOnDiscAction(self._filename, self.projects, database)


class GitHubRepository(Repository):
    def __init__(self, url: str,
                 projects: Optional[list[Project]] = None):
        super().__init__(projects)
        self._url = url

    def create_action(self, work_dir: Path, database: Database) -> RepositoryAction:
        return SourceOnGitHubAction(self._url, self.projects, database)

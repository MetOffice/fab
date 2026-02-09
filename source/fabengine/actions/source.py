from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from multiprocessing import get_logger as mp_get_logger
from os import walk as os_walk
from pathlib import Path
from subprocess import run, PIPE
from typing import Iterable
from urllib.parse import urlparse

from fabengine.actions import Action, Prerequisite, SubprocessActionException
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import (ImportFortran, PreprocessFortranAction,
                                       ImportInclusion)
from fabengine.actions.pfunit import PfUnit
from fabengine.actions.psyclone import PSyclone, PreprocessAlgorithm
from fabengine.actions.templaterator import Templaterator
from fabengine.database import Database
from fabengine.project import Project


class RepositoryAction(Action, ABC):
    @property
    @abstractmethod
    def local_copy(self) -> Path:
        raise NotImplementedError()


class SourceOnDiscAction(RepositoryAction):
    def __init__(self, remote: str, projects: list[Project],
                 database: Database):
        self._remote = remote
        self._projects = projects
        self._database = database

    def __str__(self) -> str:
        return "Source from disc: " + str(self._remote)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    @property
    def local_copy(self) -> Path:
        filename = Path(self._remote.split(':')[-1])
        return self._database.configuration.work_dir / filename.name

    def perform(self) -> Iterable[Action]:
        remote = str(self._remote).rstrip('/')
        local = str(self._database.configuration.work_dir)
        command = ['rsync', '-a', remote, local]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            raise SubprocessActionException(self, ' '.join(command),
                                            process.returncode,
                                            process.stdout, process.stderr)

        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(self.local_copy / project.source_dir,
                                project.identifier, self._database)
            )
        return actions


class SourceOnGitHubAction(RepositoryAction):
    def __init__(self, url: str, projects: list[Project],
                 database: Database):
        _, netloc, _, _, _, _ = urlparse(url)
        if netloc.split('@')[-1].lower() != 'github.com':
            raise RuntimeError(
                "URL passed to SourceOnGitHubAction is not on GitHub"
            )
        self._url = url
        self._projects = projects
        self._database = database

    def __str__(self) -> str:
        return "GitHub repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    @property
    def local_copy(self) -> Path:
        _, netloc, path, _, query, fragment = urlparse(self._url)
        name = Path(path).stem
        return self._database.configuration.work_dir / name

    def perform(self) -> list[Action]:
        repo_marker = self.local_copy / '.git'
        if repo_marker.is_dir(): # Repository is present
            command = ['git', '-C', str(self.local_copy), 'pull']
        else:  # Repository is missing
            scheme, netloc, path, _, _, fragment = urlparse(self._url)
            url = f'{scheme}://{netloc}{path}'
            command = ['git', 'clone', '--depth=1', f'--branch={fragment}',
                       url, str(self.local_copy)]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            raise SubprocessActionException(self, ' '.join(command),
                                            process.returncode,
                                            process.stdout, process.stderr)

        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(self.local_copy / project.identifier, project.identifier, self._database)
            )
        return actions


class SourceDirectory(Action):
    def __init__(self, filename: Path, tag: str, database: Database):
        self._source_dir = filename
        self._tag = tag
        self._database = database

    def __str__(self) -> str:
        return "Source directory: " + str(self._source_dir)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source_dir)]

    # Todo: Would it be possible to chunk output since this action can
    #       generate a lot of actions. Maybe create 10 (or 100) before putting
    #       ourself back on the queue. Or maybe that only seems necessary for
    #       single threaded builds.
    #
    def perform(self) -> Generator[Action, None, list[Action]]:
        mp_get_logger().debug("Scanning " + str(self._source_dir))
        project_dir = self._database.configuration.build_dir / self._tag
        project_dir.mkdir(parents=True, exist_ok=True)
        # Todo: Hardwired paths - maybe something with a factory pattern here?
        core_dir = self._database.configuration.work_dir / 'lfric_core'

        # Todo: Tree-walk not added to pathlib until v3.12.
        #
        # for root, branches, leaves in self._source_dir.walk():
        for root_str, branches, leaves in os_walk(self._source_dir):
            root = Path(root_str)
            for leaf in leaves:
                if leaf.startswith('.'):
                    continue  # Ignore "hidden" files.

                full_filename = root / leaf
                relative_filename = full_filename.relative_to(self._source_dir)

                actions: list[Action] = []
                if full_filename.suffix == '.f90':
                    actions.append(ImportFortran(self._source_dir,
                                                 relative_filename,
                                                 self._tag,
                                                 self._database))
                elif full_filename.suffix == '.F90':
                    actions.append(PreprocessFortranAction(self._source_dir,
                                                           relative_filename,
                                                           self._tag,
                                                           self._database))
                elif full_filename.suffix == '.pf':
                    # Todo: No support for per-file compiler arguments. Do we
                    #       need it?
                    actions.append(PfUnit(self._source_dir,
                                          relative_filename,
                                          self._tag,
                                          self._database))
                elif full_filename.suffix == '.t90':
                    # Todo: Hardwired to field templating and just nasty.
                    for mapping in self._database.configuration.field_instances:
                        ttype = list(mapping.keys())[0]
                        tkind = mapping[ttype]
                        leafname = full_filename.stem[:-4] + '_' + tkind + '_mod.f90'
                        inserts = {'type': ttype, 'kind': tkind}
                        actions.append(Templaterator(full_filename,
                                                     leafname,
                                                     inserts,
                                                     core_dir,
                                                     self._database))
                elif full_filename.suffix == '.X90':
                    actions.append(PreprocessAlgorithm(self._source_dir,
                                                       relative_filename,
                                                       self._tag,
                                                       self._database))
                elif full_filename.suffix == '.x90':
                    actions.append(PSyclone(self._source_dir,
                                            relative_filename,
                                            self._tag,
                                            self._database))
                elif full_filename.suffix == '.h':
                    actions.append(ImportInclusion(self._source_dir,
                                                   relative_filename,
                                                   self._tag,
                                                   self._database))
                elif full_filename.suffix == '.inc':
                    actions.append(ImportInclusion(self._source_dir,
                                                   relative_filename,
                                                   self._tag,
                                                   self._database))
                else:
                    mp_get_logger().debug("Ignoring file: " + full_filename.name)

                for action in actions:
                    yield action
        return []

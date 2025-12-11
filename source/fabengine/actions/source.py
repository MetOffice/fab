from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from multiprocessing import get_logger as mp_get_logger
from pathlib import Path
from subprocess import run, PIPE
from typing import Iterable
from urllib.parse import urlparse

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import ImportFortran, PreprocessFortranAction, ImportInclusion
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
                 work_dir: Path, database: Database):
        self._remote = remote
        self._projects = projects
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Source from disc: " + str(self._remote)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    @property
    def local_copy(self) -> Path:
        filename = Path(self._remote.split(':')[-1])
        return self._work_dir / filename.name

    def perform(self) -> Iterable[Action | ActionResult]:
        remote = str(self._remote).rstrip('/')
        local = str(self._work_dir)
        command = ['rsync', '-a', remote, local]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]

        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(
                    project.identifier,
                    self.local_copy / project.source_dir,
                    self._work_dir, self._database
                )
            )
        return actions


class SourceOnGitHubAction(RepositoryAction):
    def __init__(self, url: str, projects: list[Project],
                 work_dir: Path, database: Database):
        _, netloc, _, _, _, _ = urlparse(url)
        if netloc.split('@')[-1].lower() != 'github.com':
            raise RuntimeError(
                "URL passed to SourceOnGitHubAction is not on GitHub"
            )
        self._url = url
        self._projects = projects
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "GitHub repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    @property
    def local_copy(self) -> Path:
        _, netloc, path, _, query, fragment = urlparse(self._url)
        name = Path(path).stem
        return self._work_dir / name

    def perform(self) -> list[Action | ActionResult]:
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
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]

        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(project.identifier,
                                self.local_copy / project.identifier,
                                self._work_dir, self._database)
            )
        return actions


class SourceDirectory(Action):
    def __init__(self, tag: str, filename: Path, work_dir: Path,
                 database: Database):
        self._tag = tag
        self._source_dir = filename
        self._work_dir = work_dir
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
        build_dir = self._work_dir / 'build'
        project_dir = build_dir / self._tag
        project_dir.mkdir(parents=True, exist_ok=True)
        # Todo: Hardwired paths - maybe something with a factory pattern here?
        core_dir = self._work_dir / 'lfric_core'

        for root, branches, leaves in self._source_dir.walk():
            for leaf in leaves:
                if leaf.startswith('.'):
                    continue  # Ignore "hidden" files.

                full_filename = root / leaf
                relative_filename = full_filename.relative_to(self._source_dir)

                actions: list[Action] = []
                if full_filename.suffix == '.f90':
                    actions.append(ImportFortran(self._source_dir,
                                                 relative_filename,
                                                 project_dir,
                                                 self._work_dir,
                                                 self._database))
                elif full_filename.suffix == '.F90':
                    actions.append(PreprocessFortranAction(self._source_dir,
                                                           relative_filename,
                                                           project_dir,
                                                           self._work_dir,
                                                           self._database))
                elif full_filename.suffix == '.pf':
                    # Todo: No support for per-file compiler arguments. Do we
                    #       need it?
                    actions.append(PfUnit(full_filename, build_dir, self._database))
                elif full_filename.suffix == '.t90':
                    # Todo: Hardwired to field templating and just nasty.
                    # Todo: No support for per-file compiler arguments. Do we
                    #       need it?
                    for mapping in self._database.field_instances:
                        ttype = list(mapping.keys())[0]
                        tkind = mapping[ttype]
                        leafname = full_filename.stem[:-4] + '_' + tkind + '_mod.f90'
                        inserts = {'type': ttype, 'kind': tkind}
                        actions.append(Templaterator(full_filename,
                                                     leafname,
                                                     inserts,
                                                     project_dir,
                                                     core_dir,
                                                     self._database))
                elif full_filename.suffix == '.X90':
                    actions.append(PreprocessAlgorithm(self._source_dir,
                                                       relative_filename,
                                                       project_dir,
                                                       core_dir,
                                                       self._work_dir,
                                                       self._database))
                elif full_filename.suffix == '.x90':
                    actions.append(PSyclone(self._source_dir, relative_filename, project_dir, core_dir, self._work_dir,
                                            self._database))
                elif full_filename.suffix == '.h':
                    actions.append(ImportInclusion(self._source_dir,
                                                   relative_filename,
                                                   project_dir,
                                                   build_dir,
                                                   self._database))
                elif full_filename.suffix == '.inc':
                    actions.append(ImportInclusion(self._source_dir,
                                                   relative_filename,
                                                   build_dir))
                else:
                    mp_get_logger().debug("Ignoring file: " + full_filename.name)

                for action in actions:
                    yield action
        return []

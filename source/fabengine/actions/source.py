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
from fabengine.actions.fortran import ImportFortran, PreprocessFortran
from fabengine.actions.pfunit import PfUnit
from fabengine.actions.psyclone import PSyclone, PreprocessAlgorithm
from fabengine.actions.templaterator import Templaterator
from fabengine.database import Database
from fabengine.project import Project


class RepositoryAction(Action, ABC):
    @property
    @abstractmethod
    def working_copy(self) -> Path:
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
    def working_copy(self) -> Path:
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
                    self.working_copy / project.source_dir,
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
    def working_copy(self) -> Path:
        _, netloc, path, _, query, fragment = urlparse(self._url)
        name = Path(path).stem
        return self._work_dir / name

    def perform(self) -> list[Action | ActionResult]:
        repo_marker = self.working_copy / '.git'
        if repo_marker.is_dir(): # Repository is present
            command = ['git', '-C', str(self.working_copy), 'pull']
        else:  # Repository is missing
            scheme, netloc, path, _, _, fragment = urlparse(self._url)
            url = f'{scheme}://{netloc}{path}'
            command = ['git', 'clone', '--depth=1', f'--branch={fragment}',
                       url, str(self.working_copy)]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]

        actions: list[Action] = []
        for project in self._projects:
            actions.append(
                SourceDirectory(project.identifier,
                                self.working_copy / project.identifier,
                                self._work_dir, self._database)
            )
        return actions


class SourceDirectory(Action):
    def __init__(self, tag: str, filename: Path, work_dir: Path,
                 database: Database):
        self._tag = tag
        self._filename = filename
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Source directory: " + str(self._filename)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._filename)]

    # Todo: Would it be possible to chunk output since this action can
    #       generate a lot of actions. Maybe create 10 (or 100) before putting
    #       ourself back on the queue. Or maybe that only seems necessary for
    #       single threaded builds.
    #
    def perform(self) -> Generator[Action, None, list[Action]]:
        mp_get_logger().debug("Scanning " + str(self._filename))
        build_dir = self._work_dir / 'build' / self._tag
        # Todo: Hardwired paths - maybe something with a factory pattern here?
        core_dir = self._work_dir / 'lfric_core'
        build_dir.mkdir(parents=True, exist_ok=True)

        for root, branches, leaves in self._filename.walk():
            for leaf in leaves:
                if leaf.startswith('.'):
                    continue  # Ignore "hidden" files.

                filename = root / leaf
                actions: list[Action] = []
                if filename.suffix == '.f90':
                    actions.append(ImportFortran(filename, build_dir,
                                                 self._database))
                elif filename.suffix == '.F90':
                    actions.append(PreprocessFortran(filename, build_dir,
                                                     self._database))
                elif filename.suffix == '.pf':
                    actions.append(PfUnit(filename, build_dir, self._database))
                elif filename.suffix == '.t90':
                    # Todo: Hardwired to field templating and just nasty.
                    for mapping in self._database.field_instances:
                        ttype = list(mapping.keys())[0]
                        tkind = mapping[ttype]
                        leafname = filename.stem[:-4] + '_' + tkind + '_mod.f90'
                        inserts = {'type': ttype, 'kind': tkind}
                        actions.append(Templaterator(filename,
                                                     leafname,
                                                     inserts,
                                                     build_dir,
                                                     core_dir,
                                                     self._database))
                elif filename.suffix == '.X90':
                    actions.append(PreprocessAlgorithm(filename, build_dir,
                                                       core_dir,
                                                       self._database))
                elif filename.suffix == '.x90':
                    actions.append(PSyclone(filename, build_dir, core_dir,
                                            self._database))
                else:
                    mp_get_logger().debug("Ignoring file: " + filename.name)

                for action in actions:
                    yield action
        return []

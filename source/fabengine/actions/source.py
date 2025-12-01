from __future__ import annotations

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


class SourceDirectory(Action):
    def __init__(self, filename: Path, work_dir: Path,
                 database: Database):
        self._filename = filename
        self._work_dir = work_dir
        # self._fpp_macros = fpp_macros
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
        build_dir = self._work_dir.absolute() / 'build'
        core_dir = self._work_dir.absolute() / 'lfric_core'
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


class GitRepository(Action):
    def __init__(self, url: str, work_dir: Path,
                 database: Database):
        self._url = url
        self._work_dir = work_dir
        # self._fpp_macros = fpp_macros
        self._database = database

    def __str__(self) -> str:
        return "Git repository: " + self._url

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    def perform(self) -> list[Action]:
        scheme, netloc, path, _, query, fragment = urlparse(self._url)
        name = Path(path).stem
        repo_path = self._work_dir / name
        repo_marker = repo_path / '.git'
        if repo_marker.is_dir(): # Repository is present
            command = ['git', '-C', str(repo_path), 'pull']
        else:  # Repository is missing
            url = f'{scheme}://{netloc}{path}'
            command = ['git', 'clone', '--depth=1', f'--branch={fragment}',
                       url, str(repo_path)]
        run(command, check=True, stdout=PIPE, stderr=PIPE)

        actions: list[Action] = []
        for pair in query.split('&'):
            key, value = pair.split('=', maxsplit=1)
            if key == 'root':
                actions.append(SourceDirectory(repo_path/ value,
                                               self._work_dir, self._database))
        return actions


class RemoteTree(Action):
    def __init__(self, remote: Path, roots: list[str], work_dir: Path,
                 database: Database):
        self._remote = remote
        self._roots = roots
        self._work_dir = work_dir
#        self._fpp_macros = fpp_macros
        self._database = database

    def __str__(self) -> str:
        return "Remote tree: " + str(self._remote)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    def perform(self) -> Iterable[Action | ActionResult]:
        remote = str(self._remote).rstrip('/')
        local = str(self._work_dir)
        command = ['rsync', '-a', remote, local]
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')

        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]

        actions: list[Action] = []
        for root in self._roots:
            actions.append(
                SourceDirectory(self._work_dir / self._remote.name / root,
                                self._work_dir, self._database)
            )
        return actions

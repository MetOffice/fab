from pathlib import Path
from subprocess import run, PIPE
from typing import Iterable

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class Templaterator(Action):
    def __init__(self, filename: Path, leafname: str, inserts: dict[str, str],
                 work_dir: Path, core_dir: Path, database: Database):
        self._filename = filename
        self._leafname = leafname
        self._inserts = inserts
        self._work_dir = work_dir
        self._core_dir = core_dir
        self._database = database

    def __str__(self) -> str:
        return f"Templating: {self._filename.name}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._filename)]

    def perform(self) -> Iterable[Action | ActionResult]:
        exe = self._core_dir / 'infrastructure' / 'build' / 'tools' / 'Templaterator'
        source_file = self._work_dir / self._leafname

        command = [str(exe), '-o', str(source_file)]
        for key, value in self._inserts.items():
            command.extend(['-s', key + '=' + value])
        command.append(str(self._filename))
        run(command, stdout=PIPE, stderr=PIPE, check=True)
        return [
            AnalyseFortran(source_file, self._work_dir, self._database)
        ]
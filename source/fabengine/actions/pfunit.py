from __future__ import annotations

from os import environ as os_environ
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from subprocess import run, PIPE
from typing import Iterable

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.prerequisite import FilePrerequisite
from fabengine.actions.fortran import PreprocessFortranAction
from fabengine.database import Database


class PfUnit(Action):
    def __init__(self, source: Path, work_dir: Path,
                 database: Database):
        self._source = source
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "pFUnit: " + self._source.name

    _PROGRAM_PATTERN = re_compile(r'(\s*(:?end)?\s*program\s*)\w+(.*)',
                                  IGNORECASE)
    _MODULE_PATTERN = re_compile(r'(\s*(:?end)?\s*module\s*)loader(.*)',
                                 IGNORECASE)
    _USE_PATTERN = re_compile(r'(\s*use\s*)loader(.*)', IGNORECASE)
    _CALL_PATTERN = re_compile(r'', IGNORECASE)

    def _driver(self,
                template_path: Path,
                test_name: str,
                work_dir: Path) -> list[Action]:
        prog_name = test_name + '_prog'
        loader_name = test_name + '_loader'
        source: list[str] = []
        for line in template_path.read_text().splitlines():
            match = self._PROGRAM_PATTERN.match(line)
            if match:
                statement = match.group(1)
                tail = match.group(3) or ''
                source.append(statement + prog_name + tail)
                continue

            match = self._MODULE_PATTERN.match(line)
            if match:
                head = match.group(1)
                tail = match.group(3) or ''
                source.append(head + loader_name + tail)
                continue

            match = self._USE_PATTERN.match(line)
            if match:
                head = match.group(1)
                tail = match.group(2) or ''
                source.append(head + loader_name + tail)
                continue

            source.append(line)

        source_file = work_dir / Path(prog_name).with_suffix('.F90')
        source_file.write_text('\n'.join(source))

        include_file = work_dir / Path(prog_name).with_suffix('.inc')
        include_file.write_text(
            f"ADD_TEST_SUITE({test_name}_suite)\n"
        )

        return [
            PreprocessFortranAction(
                source_file, work_dir, self._database,
                {'_TEST_SUITES': f'"{include_file.absolute()}"'}
            ),
            RunTest(self._work_dir / prog_name)
        ]

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    def perform(self) -> list[Action]:
        actions: list[Action] = []

        pfunit_str = os_environ.get('PFUNIT')
        if pfunit_str is None:
            raise RuntimeError("PFUNIT must point to install directory")
        pfunit_path = Path(pfunit_str)
        funitproc_path = pfunit_path / 'bin' / 'funitproc'
        dest = self._work_dir / self._source.with_suffix('.F90').name
        run([str(funitproc_path), '-quiet', str(self._source), str(dest)],
            check=True)
        actions.append(PreprocessFortranAction(dest, self._work_dir,
                                               self._database))

        actions.extend(
            self._driver(
                pfunit_path / 'include' / 'driver.F90',
                self._source.stem, self._work_dir
            )
        )

        return actions


class RunTest(Action):
    def __init__(self, executable: Path):
        self._executable = executable

    def __str__(self) -> str:
        return "Execute: " + str(self._executable)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._executable)]

    def perform(self) -> list[Action | ActionResult]:
        process = run([str(self._executable)], stdout=PIPE, encoding='utf8')
        return [ActionResult(self, process.returncode,
                             process.stdout, process.stderr)]

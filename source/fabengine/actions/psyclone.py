from __future__ import annotations

from re import compile as re_compile, IGNORECASE
from pathlib import Path
from subprocess import run, PIPE
from typing import Generator, Iterable, Optional

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.prerequisite import FilePrerequisite, SymbolPrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class PreprocessAlgorithm(Action):
    def __init__(self, source: Path, work_dir: Path, core_dir: Path,
                 database: Database, macros: Optional[dict[str, str]] = None):
        self._source = source
        self._work_dir = work_dir
        self._core_dir = core_dir
        self._database = database
        if macros is None:
            self._macros = {}
        else:
            self._macros = macros

    def __str__(self) -> str:
        return "Preprocess: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source)]

    def perform(self) -> list[Action]:
        dest = self._work_dir / self._source.with_suffix('.x90').name
        command = ['cpp', '-traditional-cpp', '-P']
        for name, value in self._macros.items():
            command.extend(['-D', f'{name}={value}'])
        command.extend(['-D', 'RDEF_PRECISION=64',
                        '-D', 'R_SOLVER_PRECISION=32',
                        '-D', 'R_TRAN_PRECISION=64',
                        '-D', 'R_BL_PRECISION=64'])
        command.extend(['-D', 'LEGACY_MPI'])
        command.append(str(self._source))
        command.append(str(dest))
        run(command, check=True)
        return [PSyclone(dest, self._work_dir, self._core_dir, self._database)]


class PSyclone(Action):
    def __init__(self, algorithm: Path, work_dir: Path, core_dir: Path,
                 database: Database):
        self._algorithm = algorithm
        self._work_dir = work_dir
        self._core_dir = core_dir
        self._database = database

        all_kernels = self._find_kernels(algorithm)
        self._psy = (all_kernels != [])
        self._kernels = self._remove_builtins(all_kernels)

    def __str__(self) -> str:
        return "PSyclone: " + self._algorithm.name

    @staticmethod
    def _remove_builtins(kernels: list[str]) -> list[str]:
        new_kernels: list[str] = []
        for type_name in kernels:
            if type_name.endswith('_type'):  # Todo: Assumption
                new_kernels.append(type_name)
        return new_kernels

    # Todo: Does not cope with strings containing exclamation mark.
    _COMMENT_PATTERN = re_compile(r'(.*?)!+.*$')
    _CONTINUATION_PATTERN = re_compile(r'(.*)\s*&\s*$')

    @staticmethod
    def _consolidate_lines(fortran_source: Path) -> Generator[str, None, None]:
        buffer = ''
        state = 'single'
        for line in fortran_source.read_text().splitlines():
            # Remove comments
            match = PSyclone._COMMENT_PATTERN.match(line)
            if match:
                line = match.group(1)
            if not line.strip():  # Ignore empty lines.
                continue

            match = PSyclone._CONTINUATION_PATTERN.match(line)
            if state == 'single':
                if match:  # Continuation line
                    state = 'multiple'
                    buffer += match.group(1).strip() + ' '
                else:  # Plain line
                    yield line.strip()
                continue
            if state == 'multiple':
                if match:  # Continuation line
                    buffer += match.group(1).strip() + ' '
                else:  # Plain line
                    state = 'single'
                    buffer += line.strip()
                    yield buffer
                    buffer = ''

    _INVOKE_PATTERN = re_compile(r'\s*call\s*invoke\s*\((.+)\)',
                                 IGNORECASE)
    # Todo: Problems with parenthesis within argument lists. This solution only
    #       handles a single level of nesting.
    _PROCEDURE_PATTERN = re_compile(r'\s*(\w+)\s*\((:?.*?|\(.*\))*\)\s*,?', IGNORECASE)

    @staticmethod
    def _find_kernels(algorithm: Path) -> list[str]:
        kernels: list[str] = []
        for line in PSyclone._consolidate_lines(algorithm):
            match = PSyclone._INVOKE_PATTERN.match(line)
            if match:
                arguments = match.group(1)
                for type_match in PSyclone._PROCEDURE_PATTERN.finditer(arguments):
                    type_name = type_match.group(1).lower()
                    kernels.append(type_name)
        return kernels

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = []
        for kernel in self._kernels:
            prereqs.append(SymbolPrerequisite(kernel, self._database))
            symbol = self._database.symbol_table.get(kernel)
            if symbol:
                prereqs.append(FilePrerequisite(symbol.source_file))
        return prereqs

    def perform(self) -> list[Action | ActionResult]:
        kernel_roots: set[Path] = set()
        for kernel in self._kernels:
            kernel_symbol = self._database.symbol_table.get(kernel)
            kernel_roots.add(kernel_symbol.source_file.parent)

        command = ['psyclone', '-api', 'lfric', '-l', 'all']
        for root in kernel_roots:
            command.extend(['-d', str(root)])
        #
        # Todo: Hardwired
        #
        command.extend(['-c', str(self._core_dir / 'etc' / 'psyclone.cfg')])
        alg_name = self._algorithm.stem + '.f90'
        command.extend(['-oalg', str(self._work_dir / alg_name)])
        psy_name = self._algorithm.stem + '_psy.f90'
        command.extend(['-opsy', str(self._work_dir / psy_name)])
        command.append(str(self._algorithm))
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')

        actions : list[Action | ActionResult] = []
        if process.returncode != 0:
            actions.append(
                ActionResult(self, process.returncode,
                             ' '.join(command),
                             process.stdout, process.stderr)
            )
        else:  # Command succeeded
            actions.append(
                AnalyseFortran(self._work_dir / alg_name,
                               self._work_dir, self._database)
            )
            if self._psy:
                actions.append(AnalyseFortran(self._work_dir / psy_name,
                                              self._work_dir, self._database))
        return actions

from __future__ import annotations

from re import compile as re_compile, IGNORECASE
from pathlib import Path
from subprocess import run, PIPE
from typing import Generator, Iterable

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.actions.fortran import PreprocessFortranBase
from fabengine.prerequisite import FilePrerequisite, SymbolPrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class PreprocessAlgorithm(PreprocessFortranBase):
    def __init__(self, repo_dir: Path, source: Path, build_dir: Path,
                 core_dir: Path, work_dir: Path, database: Database):
        super().__init__(repo_dir, source, build_dir, work_dir, database)
        self._core_dir = core_dir

    def __str__(self) -> str:
        return "Preprocess algorithm: " + str(self.source)

    def perform(self) -> list[Action | ActionResult]:
        destination = self._build_dir / self.source.with_suffix('.x90')
        destination.parent.mkdir(parents=True, exist_ok=True)
        process = self.invoke_preprocessor(destination)
        if process.returncode != 0:
            return [ActionResult(self, process.returncode,
                                 ' '.join(process.args),
                                 stdout=process.stdout,
                                 stderr=process.stderr)]
        return [PSyclone(self._build_dir, self._source.with_suffix('.x90'),
                         self._build_dir, self._core_dir,
                         self._work_dir, self._database)]


class PSyclone(Action):
    def __init__(self, repo_dir: Path, algorithm_file: Path,
                 project_dir: Path, core_dir: Path,
                 work_dir: Path, database: Database):
        self._repo_dir = repo_dir
        self._algorithm_file = algorithm_file
        self._project_dir = project_dir
        self._work_dir = work_dir
        self._core_dir = core_dir
        self._database = database

        self._full_filename = self._repo_dir / self._algorithm_file

        all_kernels = self._find_kernels(self._full_filename)
        self._psy = (all_kernels != [])
        self._kernels = self._remove_builtins(all_kernels)

    def __str__(self) -> str:
        return "PSyclone: " + self._algorithm_file.name

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

    _INVOKE_PATTERN = re_compile(r'call\s*invoke\s*\((.+)\)',
                                 IGNORECASE)
    # Todo: Problems with parenthesis within argument lists. This solution only
    #       handles a single level of nesting.
    _PROCEDURE_PATTERN = re_compile(r'\s*(\w+)\s*\((:?.*?|\(.*\))*\)\s*,?', IGNORECASE)

    @staticmethod
    def _find_kernels(algorithm: Path) -> list[str]:
        kernels: list[str] = []
        for line in PSyclone._consolidate_lines(algorithm):
            match = PSyclone._INVOKE_PATTERN.search(line)
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
        kernel_roots: list[Path] = []
        for kernel in self._kernels:
            kernel_symbol = self._database.symbol_table.get(kernel)
            new_root = kernel_symbol.source_file.parent
            # Remove any directories which are children of the new one
            kernel_roots = [directory for directory in kernel_roots
                            if not directory.is_relative_to(new_root)]
            # Add new directory only if it is not a child of an existing one
            child = False
            for directory in kernel_roots:
                if new_root.is_relative_to(directory):
                    child = True
                    break
            if not child:
                kernel_roots.append(new_root)

        command = ['psyclone', '-api', 'lfric', '-l', 'all']
        for root in kernel_roots:
            command.extend(['-d', str(root)])
        #
        # Todo: Hardwired and depends on a repository which may not have been
        #       imported.
        #
        command.extend(['-c', str(self._core_dir / 'etc' / 'psyclone.cfg')])
        alg_name = self._algorithm_file.stem + '.f90'
        command.extend(['-oalg', str(self._project_dir / alg_name)])
        psy_name = self._algorithm_file.stem + '_psy.f90'
        command.extend(['-opsy', str(self._project_dir / psy_name)])
        command.append(str(self._repo_dir / self._algorithm_file))
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
                AnalyseFortran(self._project_dir / alg_name,
                               self._work_dir, self._database)
            )
            if self._psy:
                actions.append(AnalyseFortran(self._project_dir / psy_name,
                                              self._work_dir, self._database))
        return actions

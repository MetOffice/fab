from __future__ import annotations

from re import compile as re_compile, IGNORECASE
from pathlib import Path
from subprocess import run, PIPE
from typing import Generator, Iterable, Optional

from fabengine.actions import Action, Prerequisite, SubprocessActionException
from fabengine.actions.fortran import PreprocessFortranBase
from fabengine.prerequisite import FilePrerequisite, SymbolPrerequisite
from fabengine.actions.fortran import AnalyseFortran
from fabengine.database import Database


class PreprocessAlgorithm(PreprocessFortranBase):
    """
    Preprocesses an ``.X90`` algorithm file with PSyclone.
    """

    def __init__(
        self,
        repo_dir: Path,
        filename: Path,
        project: str,
        database: Database,
        extra_definitions: Optional[dict[str, str]] = None,
    ):
        """
        :param repo_dir: Source tree root.
        :param filename: Algorithm file relative to root.
        :param project: Subdirectory of workspace for resulting source.
        :param database: Build system state and configuration.
        :param extra_definitions: Additional macros to use with preprocessor.
        """
        super().__init__(repo_dir, filename, project, database, extra_definitions)
        self._project = project

    def __str__(self) -> str:
        return f"Preprocess PSyKAl algorithm: {self.repo} {self.filename}"

    def perform(self) -> list[Action]:
        """
        Performs the preprocessing.

        :return: Action to PSyclone the algorithm.
        """
        actions = super().perform()
        build_dir = self._database.configuration.build_dir
        actions.append(
            PSyclone(
                build_dir,
                self.destination_file.relative_to(build_dir),
                "",
                self._database,
            )
        )
        return actions


class PSyclone(Action):
    """
    PSyclones ``.x90`` algorithm source using PSyKAl model.

    .. todo:: No transformation scripts!
    """

    def __init__(
        self, repo_dir: Path, algorithm_file: Path, tag: str, database: Database
    ):
        """
        :param repo_dir: Source tree root.
        :param algorithm_file: Algorithm file relative to root.
        :param tag: Subdirectory of workspace for resulting source.
        :param database: Build system state and configuration.
        """
        self._repo_dir = repo_dir
        self._algorithm_file = algorithm_file
        self._tag = tag
        self._database = database

        self._source_file = self._repo_dir / self._algorithm_file

        all_kernels = self._find_kernels(self._source_file)
        self._psy = all_kernels != []
        self._kernels = self._remove_builtins(all_kernels)

    def __str__(self) -> str:
        return "PSyclone: " + self._algorithm_file.name

    @staticmethod
    def _remove_builtins(kernels: list[str]) -> list[str]:
        # Todo: Discussion is underway with PSyclone developers to extend the
        #       API to provide this information so a clumbsy heuristic is
        #       unnecessary.
        new_kernels: list[str] = []
        for type_name in kernels:
            if type_name.endswith("_type"):  # Todo: Assumption
                new_kernels.append(type_name)
        return new_kernels

    # Todo: Does not cope with strings containing exclamation mark.
    _COMMENT_PATTERN = re_compile(r"(.*?)!+.*$")
    _CONTINUATION_PATTERN = re_compile(r"(.*)\s*&\s*$")

    @staticmethod
    def _consolidate_lines(fortran_source: Path) -> Generator[str, None, None]:
        buffer = ""
        state = "single"
        for line in fortran_source.read_text().splitlines():
            # Remove comments
            match = PSyclone._COMMENT_PATTERN.match(line)
            if match:
                line = match.group(1)
            if not line.strip():  # Ignore empty lines.
                continue

            match = PSyclone._CONTINUATION_PATTERN.match(line)
            if state == "single":
                if match:  # Continuation line
                    state = "multiple"
                    buffer += match.group(1).strip() + " "
                else:  # Plain line
                    yield line.strip()
                continue
            if state == "multiple":
                if match:  # Continuation line
                    buffer += match.group(1).strip() + " "
                else:  # Plain line
                    state = "single"
                    buffer += line.strip()
                    yield buffer
                    buffer = ""

    _INVOKE_PATTERN = re_compile(r"call\s*invoke\s*\((.+)\)", IGNORECASE)
    # Todo: Problems with parenthesis within argument lists. This solution only
    #       handles a single level of nesting.
    _PROCEDURE_PATTERN = re_compile(r"\s*(\w+)\s*\((:?.*?|\(.*\))*\)\s*,?", IGNORECASE)

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
        """
        Determines prerequisite rules.

        .. todo:: Does it need to depend on both symbols and files?

        :return: Depends on symbols and source files.
        """
        prereqs: list[Prerequisite] = []
        for kernel in self._kernels:
            prereqs.append(SymbolPrerequisite(kernel, self._database))
            symbol = self._database.symbol_table.get(kernel)
            if symbol:
                prereqs.append(FilePrerequisite(symbol.source_file))
        prereqs.append(FilePrerequisite(self._database.configuration.psyclone_config))
        return prereqs

    def perform(self) -> list[Action]:
        """
        Performs the transformation.

        :return: Result if transformation failed, otherwise analysis of
                 generated source.
        """
        kernel_roots: list[Path] = []
        for kernel in self._kernels:
            kernel_symbol = self._database.symbol_table.get(kernel)
            assert kernel_symbol is not None
            new_root = kernel_symbol.source_file.parent
            # Remove any directories which are children of the new one
            kernel_roots = [
                directory
                for directory in kernel_roots
                if not directory.is_relative_to(new_root)
            ]
            # Add new directory only if it is not a child of an existing one
            child = False
            for directory in kernel_roots:
                if new_root.is_relative_to(directory):
                    child = True
                    break
            if not child:
                kernel_roots.append(new_root)

        command = ["psyclone", "-api", "lfric", "-l", "all"]
        for root in kernel_roots:
            command.extend(["-d", str(root)])
        project_dir = (
            self._database.configuration.build_dir
            / self._tag
            / self._algorithm_file.parent
        )
        project_dir.mkdir(parents=True, exist_ok=True)
        command.extend(["-c", str(self._database.configuration.psyclone_config)])
        alg_name = self._algorithm_file.with_suffix(".f90").name
        command.extend(["-oalg", str(project_dir / alg_name)])
        psy_name = self._algorithm_file.stem + "_psy.f90"
        command.extend(["-opsy", str(project_dir / psy_name)])
        command.append(str(self._repo_dir / self._algorithm_file))
        process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8")

        actions: list[Action] = []
        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )
        else:  # Command succeeded
            actions.append(AnalyseFortran(project_dir / alg_name, self._database))
            if self._psy:
                actions.append(AnalyseFortran(project_dir / psy_name, self._database))
        return actions

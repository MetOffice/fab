from __future__ import annotations

from collections.abc import Generator, Iterable
from pathlib import Path
from re import IGNORECASE
from re import compile as re_compile

from fabengine.actions import Action, Prerequisite, SubprocessAction, TwoPartPath
from fabengine.actions.file import MapFile
from fabengine.actions.fortran import AnalyseFortran, PreprocessFortranBase
from fabengine.artefact_store import ArtefactPath
from fabengine.database import Database
from fabengine.prerequisite import (
    ArtefactPrerequisite,
    RealFilePrerequisite,
    SymbolPrerequisite,
)


class MapAlgorithm(MapFile):
    """
    Maps a PSyKAl algorithm into the virtual filesystem.
    """

    def perform(self) -> list[Action]:
        """
        Performs the copy.

        :return: An AnalyseFortran object for the new file.
        """
        actions = super().perform()
        actions.append(PSyclone(self.artefact_path, self._database))
        return actions


class PreprocessAlgorithm(PreprocessFortranBase):
    """
    Preprocesses an ``.X90`` algorithm file with PSyclone.
    """

    def __init__(
        self,
        filename: TwoPartPath,
        project: str,
        encoding: str,
        database: Database,
        extra_definitions: dict[str, str] | None = None,
    ):
        """
        :param filename: Algorithm file.
        :param project: Subdirectory of workspace for resulting source.
        :param database: Build system state and configuration.
        :param extra_definitions: Additional macros to use with preprocessor.
        """
        super().__init__(
            filename,
            project,
            encoding,
            database,
            macros=extra_definitions or {},
            force_include_dir=[],
            kind="PSyKAl algorithm",
        )

    def perform(self) -> list[Action]:
        """
        Performs the preprocessing.

        :return: Action to PSyclone the algorithm.
        """
        super().preprocess_file()
        return [PSyclone(self.destination_file, self._database)]


class PSyclone(SubprocessAction):
    """
    PSyclones ``.x90`` algorithm source using PSyKAl model.

    .. todo:: No transformation scripts!
    """

    def __init__(self, virtual_filename: ArtefactPath, database: Database):
        """
        :param virtual_filename: Algorithm file.
        :param database: Build system state and configuration.
        """
        self._virtual_filename = virtual_filename
        self._database = database

        self._algorithm_path = self._virtual_filename.with_suffix(".f90")
        all_kernels = self._find_kernels(
            self._database.artefact_store.get_artefact(
                self._virtual_filename
            ).real_filename
        )
        self._psy = all_kernels != []
        psy_name = self._virtual_filename.stem + "_psy.f90"
        self._psy_path = self._virtual_filename.with_name(psy_name)
        self._kernels = self._remove_builtins(all_kernels)

        arguments = [
            "-api",
            "lfric",
            "-l",
            "all",
            "-c",
            self._database.configuration["paths"]["psyclone_config"],
        ]

        arguments.extend(
            [
                "-oalg",
                self._database.artefact_store.get_artefact(
                    self._algorithm_path
                ).real_filename,
            ]
        )
        arguments.extend(
            [
                "-opsy",
                self._database.artefact_store.get_artefact(
                    self._psy_path
                ).real_filename,
            ]
        )
        arguments.append(
            self._database.artefact_store.get_artefact(
                self._virtual_filename
            ).real_filename
        )
        super().__init__(Path("psyclone"), arguments)

    def __str__(self) -> str:
        return f"PSyclone <{self._virtual_filename}>"

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
                prereqs.append(ArtefactPrerequisite(symbol.source_file, self._database))
        prereqs.append(
            RealFilePrerequisite(
                self._database.configuration["paths"]["psyclone_config"]
            )
        )
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

            # Kernels are promoted to the working space so PSyclone can find
            # them.
            #
            self._database.artefact_store.promote_artefact(kernel_symbol.source_file)

            # Todo: I suspect there is an opportunity for optimisation here.
            #
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

        arguments: list[str] = []
        for root in kernel_roots:
            arguments.extend(
                ["-d", self._database.artefact_store.ensure_directory(root)]
            )
        self.run_subprocess(additional_arguments=arguments)
        actions: list[Action] = [AnalyseFortran(self._algorithm_path, self._database)]
        if self._psy:
            actions.append(AnalyseFortran(self._psy_path, self._database))
        return actions

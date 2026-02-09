from __future__ import annotations

from abc import ABC
from multiprocessing import get_logger as mp_get_logger
from os import environ as os_environ
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from subprocess import run, PIPE
from typing import Optional, Iterable

from fabengine.actions import Action, SubprocessActionException, Prerequisite
from fabengine.actions.file import ImportFile
from fabengine.database import (
    Database,
    PrerequisiteType,
    PrerequisiteInfo,
    SymbolType,
    SymbolInfo,
)
from fabengine.prerequisite import (
    AnalysedPrerequisite,
    FilePrerequisite,
    InclusionPrerequisite,
)


class ImportFortran(ImportFile):
    def __str__(self) -> str:
        return f"Import Fortran: {self.repo_dir} {self.filename}"

    def perform(self) -> list[Action]:
        actions = super().perform()
        actions.append(AnalyseFortran(self.destination_file, self._database))
        return actions


class ImportInclusion(ImportFile):
    def __str__(self) -> str:
        return f"Import inclusion: {self.source_file}"

    def perform(self) -> list[Action]:
        actions = super().perform()
        if Path(self.destination_file.name) not in self._database.inclusions:
            filename = Path(self.destination_file.name)
            self._database.inclusions[filename] = self.destination_file
        else:
            raise SubprocessActionException(
                self,
                command=self.command,
                return_code=-1,
                stderr=f"Duplicate inclusion '{self.destination_file.name} found",
            )
        return actions


# Todo: Implement our own preprocessor in Python allowing us to hold on to the
#       parse tree between determining prerequisites and generating output.
#
class PreprocessFortranBase(Action, ABC):
    def __init__(
        self,
        repo_dir: Path,
        filename: Path,
        project: str,
        database: Database,
        extra_definitions: Optional[dict[str, str]] = None,
    ):
        self._repo_dir = repo_dir
        self._filename = filename
        self._project = project
        self._database = database
        self._extra_definitions = extra_definitions or {}

        self._prereqs: list[Prerequisite] = []
        for name in self._determine_prereqs(self.source_file):
            self._prereqs.append(InclusionPrerequisite(Path(name), self._database))
        self._prereqs.append(FilePrerequisite(self.source_file))

    @property
    def repo(self) -> Path:
        return self._repo_dir

    @property
    def filename(self) -> Path:
        return self._filename

    @property
    def source_file(self) -> Path:
        return self._repo_dir / self._filename

    @property
    def destination_file(self) -> Path:
        suffix = self._filename.suffix.lower()
        return (
            self._database.configuration.build_dir
            / self._project
            / self._filename.with_suffix(suffix)
        )

    _INCLUDE_PATTERN = re_compile(r'\s*#include\s+(?P<quote>[\'"])(.+?)(?P=quote)')

    def _determine_prereqs(self, filename: Path) -> list[Path]:
        inclusions: set[Path] = set()
        for line in filename.read_text().splitlines():
            match = self._INCLUDE_PATTERN.match(line)
            if match:
                include_file = match.group(2)
                inclusions.add(Path(include_file))
        return list(inclusions)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return self._prereqs

    def perform(self) -> list[Action]:
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        # Todo: Hardwired command
        command = ["cpp", "-traditional-cpp", "-P"]
        for name, value in self._database.configuration.fpp_definitions.items():
            command.append(f"-D{name}={value}")
        for name, value in self._extra_definitions.items():
            command.append(f"-D{name}={value}")

        inclusion_dirs: set[Path] = set()
        for prereq in self._prereqs:
            if isinstance(prereq, InclusionPrerequisite):
                inclusion_dirs.add(self._database.inclusions[prereq.filename].parent)
        for directory in inclusion_dirs:
            command.append("-I" + str(directory))

        command.append(str(self.source_file))
        command.append(str(self.destination_file))
        process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8")
        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )
        return []


class PreprocessFortranAction(PreprocessFortranBase):
    def __init__(
        self,
        repo_dir: Path,
        filename: Path,
        tag: str,
        database: Database,
        extra_definitions: Optional[dict[str, str]] = None,
    ):
        super().__init__(repo_dir, filename, tag, database, extra_definitions)
        self._tag = tag

    def __str__(self) -> str:
        return "Preprocess Fortran: " + str(self.source_file)

    def perform(self) -> list[Action]:
        actions = super().perform()
        actions.append(AnalyseFortran(self.destination_file, self._database))
        return actions


class AnalyseFortran(Action):
    # Todo: This pattern does not handle exclamation marks in quotes.
    _COMMENT_PATTERN = re_compile(r"(.*?)![^$].*$")
    _UNIT_PATTERN = re_compile(
        r"\s*(module(?!\s*procedure)|program|function|subroutine)\s*(\w+)", IGNORECASE
    )
    # This assumes labeled "end" statements
    _END_PATTERN = re_compile(
        r"\s*end\s*(module|program|function|subroutine)(?:\s*(\w+))?", IGNORECASE
    )
    #
    # Fortran does not require spaces between keywords but that means many
    # things may only be determined by context. In the absence of a full syntax
    # parser we use the slightly clunky assumption that there will be a space
    # after "use" statements. This disambiguates the variable "use_xios".
    #
    _USE_PATTERN = re_compile(r"\s*(!\$\s*)?use\s+(\w+)", IGNORECASE)
    _EXTERNAL_PATTERN = re_compile(
        r"\s*type\s*\(\w+\),\s*external\s*::\s*(\w+)", IGNORECASE
    )
    _TYPE_PATTERN = re_compile(r"\s*type\s*,\s*public(:?.*?)::\s*(\w+)", IGNORECASE)
    _PUBLIC_PATTERN = re_compile(r"\s*public\s*(:?::)?\s*(.+)", IGNORECASE)
    _UM_DEPENDS_ON_PATTERN = re_compile(r"\s*!\s*DEPENDS\s*ON\s*:\s*(\w+)", IGNORECASE)

    def __init__(self, source: Path, database: Database):
        self._source = source
        self._database = database

    @property
    def source(self) -> Path:
        return self._source

    def __str__(self) -> str:
        return "Analyse: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source)]

    def perform(self) -> list[Action]:
        logger = mp_get_logger()

        actions: list[Action] = []

        unit_prereqs: dict[str, PrerequisiteInfo] = {}
        current_unit: Optional[str] = None
        state = "seeking"
        for line in self._source.read_text().splitlines():
            # Strip comments, does not handle exclamation marks in quotes.
            match = self._COMMENT_PATTERN.match(line)
            if match:
                # We need a special case for UM-era "depends on" comments
                second_match = self._UM_DEPENDS_ON_PATTERN.match(line)
                if second_match:
                    pass
                else:
                    line = match.group(1)

            if state == "seeking":
                match = self._UNIT_PATTERN.match(line)
                if match:
                    unit = match.group(1).lower()
                    name = match.group(2).lower()
                    logger.debug("Found unit: " + name)

                    if name in self._database.symbol_table:
                        raise RuntimeError(
                            f"Duplicate unit '{name}' "
                            f"found in {self._source.name}. Previously seen in "
                            + self._database.symbol_table[name].source_file.name
                        )

                    info = SymbolInfo(name, SymbolType[unit.upper()], self._source)
                    self._database.symbol_table[name] = info

                    current_unit = name

                    if unit == "program":
                        actions.append(DetermineFortranProgram(name, self._database))

                    state = "in unit"

            elif state == "in unit":
                match = self._TYPE_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()
                    info = SymbolInfo(name, SymbolType.TYPE, self._source)
                    self._database.symbol_table[name] = info
                    logger.debug("Found type: " + name)
                    continue

                match = self._PUBLIC_PATTERN.match(line)
                if match:
                    for symbol in match.group(2).lower().split(","):
                        symbol = symbol.strip()
                        info = SymbolInfo(symbol, SymbolType.PROCEDURE, self._source)
                        self._database.symbol_table[symbol] = info
                        logger.debug("Found procedure: " + symbol)
                        continue

                match = self._USE_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()
                    open_mp = match.group(1) or ""
                    open_mp = "OpenMP " if open_mp.strip() else ""
                    if open_mp and not self._database.configuration.use_open_mp:
                        continue

                    if name in self._database.configuration.fc_ignore_modules:
                        continue
                    if name not in unit_prereqs:
                        logger.debug(f"Found {open_mp}usage: {name}")
                        unit_prereqs[name] = PrerequisiteInfo(
                            name, PrerequisiteType.USE
                        )
                    continue

                match = self._EXTERNAL_PATTERN.match(line)
                if match:
                    name = match.group(1).lower()
                    if name not in unit_prereqs:
                        logger.debug("Found external: " + name)
                        unit_prereqs[name] = PrerequisiteInfo(
                            name, PrerequisiteType.EXTERNAL
                        )
                    continue

                match = self._UM_DEPENDS_ON_PATTERN.match(line)
                if match:
                    symbol = match.group(1).lower()
                    if symbol not in unit_prereqs:
                        logger.debug("Found UM dependency comment: " + symbol)
                        unit_prereqs[symbol] = PrerequisiteInfo(
                            symbol, PrerequisiteType.UM
                        )
                    continue

                match = self._END_PATTERN.match(line)
                if match:
                    scope_type = match.group(1).lower()
                    name = (match.group(2) or "").lower()

                    assert current_unit is not None
                    # We have to cope with the situation where a module end is
                    # unnamed.
                    if name == current_unit or scope_type == "module":
                        logger.debug("End of unit: " + name)

                        self._database.prerequisites[current_unit] = list(
                            unit_prereqs.values()
                        )

                        current_unit = None

                        state = "seeking"
                    continue
        return actions


class DetermineFortranProgram(Action):
    def __init__(self, name: str, database: Database):
        self._name = name
        self._database = database

        self._modules: set[str] = set()
        self._units = {name}

    def __str__(self) -> str:
        return f"DetermineProgram '{self._name}': {len(self._units)}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        # Todo: Can (and should) this be dynamic based on the current state of
        #       the scan?
        return [AnalysedPrerequisite(self._name, self._database)]

    def perform(self) -> list[Action]:
        actions: list[Action] = []

        new_units: set[str] = set()  # New set to avoid infinite loop
        while self._units:
            unit_name = self._units.pop()
            mp_get_logger().debug("Considering: " + unit_name)
            if unit_name in self._database.prerequisites:
                if unit_name in self._modules:
                    mp_get_logger().debug("Is module: " + unit_name)
                    continue
                self._modules.add(unit_name)

                source = self._database.symbol_table[unit_name].source_file
                prereqs = self._database.prerequisites[unit_name]
                actions.append(CompileFortran(source, prereqs, self._database))

                for prereq in self._database.prerequisites[unit_name]:
                    new_units.add(prereq.name)
            else:  # Unit has not yet been analysed
                mp_get_logger().debug("Not yet seen: " + unit_name)
                new_units.add(unit_name)
        self._units = new_units

        if len(self._units) == 0:
            actions.append(LinkFortran(self._name, self._modules, self._database))
        else:
            mp_get_logger().debug(f"Missing: {', '.join(self._units)}")
            actions.append(self)
        return actions


class CompileFortran(Action):
    def __init__(
        self,
        source: Path,
        prerequisites: Iterable[PrerequisiteInfo],
        database: Database,
    ):
        self._source = source
        self._prerequisites = set(prerequisites)
        self._database = database

    def __str__(self) -> str:
        return "Compile: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = []
        for symbol in self._prerequisites:
            if symbol.nature == PrerequisiteType.USE:
                name = Path(symbol.name).with_suffix(".mod").name
                module_file = self._database.configuration.module_dir / name
                prereqs.append(FilePrerequisite(module_file))
            elif symbol.nature == PrerequisiteType.EXTERNAL:
                pass  # The compiler doesn't interrogate externals
            elif symbol.nature == PrerequisiteType.UM:
                pass  # Nor does it interrogate UM-era dependency comments
            else:
                raise RuntimeError(
                    f"Unrecognised prerequisite type '{symbol.nature}'of {symbol.name}."
                )
        return prereqs

    def perform(self) -> Iterable[Action]:
        # Todo: Hardwired assumption on workspace layout
        extra_arguments: list[str] = []
        relative_path = self._source.relative_to(self._database.configuration.build_dir)
        for case, tags in self._database.configuration.tag_dirs.items():
            if relative_path.is_relative_to(case):
                for tag in tags:
                    extra_arguments.extend(
                        self._database.configuration.build_tag_args[tag]
                    )
        mp_get_logger().debug("Special arguments: " + ", ".join(extra_arguments))

        destination = self._source.with_suffix(".o")
        # Todo: Hardwired arguments
        command = [
            "mpif90",
            "-c",
            "-J",
            str(self._database.configuration.module_dir),
            "-fopenmp",
            "-std=f2008",
            "-ffree-line-length-none",
        ]
        for arg in os_environ["FFLAGS"].split():
            command.append(arg)
        command.extend(extra_arguments)
        #
        # Todo: Hardwired arguments
        #
        command.append("-fallow-argument-mismatch")
        command.extend([str(self._source), "-o", str(destination)])
        process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8")
        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )
        return []


class LinkFortran(Action):
    def __init__(self, program: str, modules: set[str], database: Database):
        self._program = program
        self._modules = modules
        self._database = database

    def __str__(self) -> str:
        return "Link: " + self._program

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = []
        for module in self._modules:
            if module in self._database.symbol_table:
                object_file = self._database.symbol_table[
                    module
                ].source_file.with_suffix(".o")
                prereqs.append(FilePrerequisite(object_file))
            else:  # Module has not yet been analysed
                prereqs.append(AnalysedPrerequisite(module, self._database))
        return prereqs

    def perform(self) -> list[Action]:
        objects: set[Path] = set()
        for module in self._modules:
            object_file = self._database.symbol_table[module].source_file.with_suffix(
                ".o"
            )
            objects.add(object_file)

        dest = self._database.configuration.work_dir / self._program
        command = ["mpif90"]
        for arg in os_environ["LDFLAGS"].split():
            command.append(arg)
        command.extend(["-o", str(dest), "-fopenmp"])
        for object_file in objects:
            command.append(str(object_file))
        for library in self._database.configuration.libraries:
            command.extend(["-l", library])
        process = run(command, stdout=PIPE, stderr=PIPE, encoding="utf8")
        if process.returncode != 0:
            raise SubprocessActionException(
                self,
                " ".join(command),
                process.returncode,
                process.stdout,
                process.stderr,
            )
        return []

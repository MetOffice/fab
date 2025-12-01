from __future__ import annotations

from collections.abc import Iterable
from multiprocessing import get_logger as mp_get_logger
from os import environ as os_environ
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from shutil import copyfile
from subprocess import run, PIPE
from typing import Optional

from fabengine.actions import Action, ActionResult, Prerequisite
from fabengine.database import (Database,
                                PrerequisiteType, PrerequisiteInfo,
                                SymbolType, SymbolInfo)
from fabengine.prerequisite import AnalysedPrerequisite, FilePrerequisite


class ImportFortran(Action):
    def __init__(self, source: Path, work_dir: Path, database: Database):
        self._source = source
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Import: " + str(self._source)

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source)]

    def perform(self) -> Iterable[Action | ActionResult]:
        destination = self._work_dir / self._source.with_suffix('.f90').name
        copyfile(self._source, destination)
        return [AnalyseFortran(destination, self._work_dir, self._database)]


class AnalyseFortran(Action):
    # Todo: This pattern does not handle exclamation marks in quotes.
    _COMMENT_PATTERN = re_compile(r'(.*?)!+.*$')
    _UNIT_PATTERN = re_compile(
        r'\s*(module(?!\s*procedure)|program|function|subroutine)\s*(\w+)',
        IGNORECASE
    )
    # This assumes labeled "end" statements
    _END_PATTERN = re_compile(
        r'\s*end\s*(module|program|function|subroutine)\s*(\w+)',
        IGNORECASE
    )
    #
    # Fortran does not require spaces between keywords but that means many
    # things may only be determined by context. In the absence of a full syntax
    # parser we use the slightly clunky assumption that there will be a space
    # after "use" statements. This disambiguates the variable "use_xios".
    #
    _USE_PATTERN = re_compile(r'\s*use\s+(\w+)', IGNORECASE)
    _EXTERNAL_PATTERN = re_compile(
        r'\s*type\s*\(\w+\),\s*external\s*::\s*(\w+)', IGNORECASE
    )
    _TYPE_PATTERN = re_compile(r'\s*type\s*,\s*public(:?.*?)::\s*(\w+)',
                               IGNORECASE)
    _PUBLIC_PATTERN = re_compile(r'\s*public\s*(:?::)?\s*(.+)', IGNORECASE)

    def __init__(self, source: Path, work_dir: Path, database: Database):
        self._source = source.absolute()
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Analyse: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source)]

    def perform(self) -> list[Action]:
        logger = mp_get_logger()

        actions: list[Action] = []

        unit_prereqs: dict[str, PrerequisiteInfo] = {}
        current_unit: Optional[str] = None
        state = 'seeking'
        for line in self._source.read_text().splitlines():
            # Strip comments, does not handle exclamation marks in quotes.
            match = self._COMMENT_PATTERN.match(line)
            if match:
                line = match.group(1)

            if state == 'seeking':
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

                    info = SymbolInfo(name, SymbolType(unit), self._source)
                    self._database.symbol_table[name] = info

                    current_unit = name

                    if unit == 'program':
                        actions.append(DetermineProgram(name, self._work_dir,
                                                        self._database))

                    state = 'in unit'

            elif state == 'in unit':
                match = self._TYPE_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()
                    info = SymbolInfo(name, SymbolType.TYPE, self._source)
                    self._database.symbol_table[name] = info
                    logger.debug("Found type: " + name)
                    continue

                match = self._PUBLIC_PATTERN.match(line)
                if match:
                    for symbol in match.group(2).lower().split(','):
                        symbol = symbol.strip()
                        info = SymbolInfo(symbol,
                                          SymbolType.PROCEDURE,
                                          self._source)
                        self._database.symbol_table[symbol] = info
                        logger.debug("Found procedure: " + symbol)
                        continue

                match = self._USE_PATTERN.match(line)
                if match:
                    name = match.group(1).lower()
                    if name in self._database.fc_ignore_modules:
                        continue
                    if name not in unit_prereqs:
                        logger.debug("Found usage: " + name)
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

                match = self._END_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()

                    if name == current_unit:
                        logger.debug("End of unit: " + name)

                        self._database.prerequisites[current_unit] \
                            = list(unit_prereqs.values())

                        current_unit = None

                        state = 'seeking'
                    continue
        return actions


class DetermineProgram(Action):
    def __init__(self, name: str, work_dir: Path,
                 database: Database):
        self._name = name
        self._work_dir = work_dir
        self._database = database

        self._modules: set[str] = set()
        self._units = {name}

    def __str__(self) -> str:
        return f"DetermineProgram '{self._name}': {len(self._units)}"

    def prerequisites(self) -> Iterable[Prerequisite]:
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
                actions.append(CompileFortran(source, self._work_dir,
                                              prereqs, self._database))

                for prereq in self._database.prerequisites[unit_name]:
                    new_units.add(prereq.name)
            else:  # Unit has not yet been analysed
                mp_get_logger().debug("Not yet seen: " + unit_name)
                new_units.add(unit_name)
        self._units = new_units

        if len(self._units) == 0:
            actions.append(LinkFortran(self._name, self._modules,
                                       self._work_dir, self._database))
        else:
            mp_get_logger().debug(f"Missing: {', '.join(self._units)}")
            actions.append(self)
        return actions


class CompileFortran(Action):
    def __init__(self, source: Path, work_dir: Path,
                 prerequisites: Iterable[PrerequisiteInfo],
                 database: Database):
        self._source = source.absolute()
        self._work_dir = work_dir.absolute()
        self._prerequisites = set(prerequisites)
        self._database = database

    def __str__(self) -> str:
        return "Compile: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = []
        for symbol in self._prerequisites:
            if symbol.nature == PrerequisiteType.USE:
                module_file = self._work_dir / Path(symbol.name).with_suffix('.mod').name
                prereqs.append(FilePrerequisite(module_file))
            elif symbol.nature == PrerequisiteType.EXTERNAL:
                pass  # The compiler doesn't interrogate externals
            else:
                raise RuntimeError(
                    f"Unrecognised prerequisite type '{symbol.nature}'"
                    f"of {symbol.name}."
                )
        return prereqs

    def perform(self) -> Iterable[Action | ActionResult]:
        dest = self._work_dir / self._source.with_suffix('.o').name
        # Todo: Hardwired arguemnts
        command = ['mpif90', '-c', '-J', str(self._work_dir), '-fopenmp',
                   '-std=f2008', '-ffree-line-length-none']
        for arg in os_environ['FFLAGS'].split():
            command.append(arg)
        #
        # Todo: Hardwired arguments
        #
        command.append('-fallow-argument-mismatch')
        command.extend([str(self._source), '-o', str(dest)])
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        actions: list[Action | ActionResult] = []
        if process.returncode != 0:
            actions.append(ActionResult(self, process.returncode,
                                        ' '.join(command),
                                        process.stdout, process.stderr))
        return actions


class PreprocessFortran(Action):
    def __init__(self, source: Path, work_dir: Path, database: Database):
        self._source = source
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Preprocess: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [FilePrerequisite(self._source)]

    def perform(self) -> list[Action | ActionResult]:
        dest = self._work_dir / self._source.with_suffix('.f90').name
        # Todo: Hardwired command
        command = ['cpp', '-traditional-cpp', '-P']
        for name, value in self._database.fpp_variables.items():
            command.extend([f'-D{name}={value}'])
        command.append(str(self._source))
        command.append(str(dest))
        process = run(command, stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 stdout=process.stdout, stderr=process.stderr)]
        return [AnalyseFortran(dest, self._work_dir, self._database)]


class LinkFortran(Action):
    def __init__(self, program: str, modules: set[str], work_dir: Path,
                 database: Database):
        self._program = program
        self._modules = modules
        self._work_dir = work_dir
        self._database = database

    def __str__(self) -> str:
        return "Link: " + ', '.join([thing for thing in self._modules])

    def prerequisites(self) -> Iterable[Prerequisite]:
        prereqs: list[Prerequisite] = []
        for module in self._modules:
            # Todo: Surely we don't need to know if the source has been analysed?
            prereqs.append(AnalysedPrerequisite(module, self._database))
            if module in self._database.symbol_table:
                filename = self._database.symbol_table[module].source_file.with_suffix('.o').name
                object_file = self._work_dir / filename
                prereqs.append(FilePrerequisite(object_file))
        return prereqs

    def perform(self) -> list[Action | ActionResult]:
        objects: set[Path] = set()
        for module in self._modules:
            filename = self._database.symbol_table[module].source_file.with_suffix('.o').name
            object_file = self._work_dir / filename
            objects.add(object_file)

        dest = self._work_dir.absolute() / self._program
        command = ['mpif90']
        for arg in os_environ['LDFLAGS'].split():
            command.append(arg)
        command.extend(['-o', str(dest), '-fopenmp'])
        for object_file in objects:
            command.append(str(object_file))
        for library in self._database.libraries:
            command.extend(['-l', library])
        process = run(command, cwd=self._work_dir,
                      stdout=PIPE, stderr=PIPE, encoding='utf8')
        if process.returncode != 0:
            return [ActionResult(self, process.returncode, ' '.join(command),
                                 process.stdout, process.stderr)]
        return []

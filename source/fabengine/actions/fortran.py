from __future__ import annotations

from abc import ABC
from multiprocessing import get_logger as mp_get_logger
from os import environ as os_environ
from pathlib import Path
from re import compile as re_compile, IGNORECASE
from typing import Optional, Iterable

from fabengine.actions import (
    Action,
    Prerequisite,
    SubprocessAction,
    SubprocessActionException,
    TwoPartPath,
)
from fabengine.actions.file import ImportFile
from fabengine.database import (
    Database,
    PrerequisiteType,
    PrerequisiteInfo,
    SymbolType,
    SymbolInfo,
)
from fabengine.package import LinkerPath, LibraryName
from fabengine.prerequisite import (
    AnalysedPrerequisite,
    FilePrerequisite,
    InclusionPrerequisite,
)


class ImportFortran(ImportFile):
    """
    Copies Fortran source into workspace.
    """

    def __init__(self, filename: TwoPartPath, tag: str, database: Database):
        super().__init__(filename, tag, database, kind="Fortran")

    def perform(self) -> list[Action]:
        """
        Performs the copy.

        :return: An AnalyseFortran object for the new file.
        """
        actions = super().perform()
        actions.append(AnalyseFortran(self.destination, self._database))
        return actions


class ImportInclusion(ImportFile):
    """
    Copies a file for inclusion into the workspace.
    """

    def __init__(self, filename: TwoPartPath, tag: str, database: Database):
        super().__init__(filename, tag, database, kind="inclusion")

    def perform(self) -> list[Action]:
        """
        Performs the copy.

        :return: If a file of that name already exists an error ActionResult.
        """
        actions = super().perform()
        if Path(self.destination.name) not in self._database.inclusions:
            filename = Path(self.destination.name)
            self._database.inclusions[filename] = self.destination
        else:
            raise SubprocessActionException(
                self,
                command=f"cp {self.source} {self.destination}",
                return_code=-1,
                stderr=f"Duplicate inclusion '{self.destination.name} found",
            )
        return actions


class PreprocessFortranBase(SubprocessAction, ABC):
    """
    Generates a Fortran source file in the workspace using the preprocessor.

    .. todo:: Implement our own preprocessor in Python allowing us to hold on
              to the parse tree between determining prerequisites and
              generating output.
    """

    def __init__(
        self,
        fortran_file: TwoPartPath,
        project: str,
        database: Database,
        extra_definitions: Optional[dict[str, str]] = None,
        kind="Fortran",
    ):
        """
        :param fortran_file: Source file as root and branch.
        :param project: Name under which to collect source in workspace.
        :param database: Build system state and configuration.
        :param extra_definitions: Additional macros to use with this preprocess.
        """
        self._fortran_file = fortran_file
        self._project = project
        self._database = database
        self._extra_definitions = extra_definitions or {}
        self._kind = kind

        self._prereqs: list[Prerequisite] = []
        for filename in self._determine_prereqs(self._fortran_file.full):
            self._prereqs.append(InclusionPrerequisite(filename, self._database))
        self._prereqs.append(FilePrerequisite(self._fortran_file.full))

        # Todo: Hardwired command
        arguments = ["-traditional-cpp", "-P"]

        for name, value in self._database.build_config["fpp_definitions"].items():
            arguments.append(f"-D{name}={value}")

        for name, value in self._extra_definitions.items():
            arguments.append(f"-D{name}={value}")

        arguments.append(str(self._fortran_file.full))
        arguments.append(str(self.destination_file))

        super().__init__(Path("cpp"), arguments)

    def __str__(self) -> str:
        return f"Preprocess {self._kind} <{self._fortran_file.branch}>"

    @property
    def destination_file(self) -> Path:
        """
        :return: Full path to destination file.
        """
        suffix = self._fortran_file.branch.suffix.lower()
        return (
            self._database.script_config["paths"]["build_dir"]
            / self._project
            / self._fortran_file.branch.with_suffix(suffix)
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
        """
        Performs the preprocessing.

        :return: An ActionResult if the preprocessor fails.
        """
        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        self.run_subprocess()
        return []


class PreprocessFortranAction(PreprocessFortranBase):
    """
    Preprocesses Fortran source.
    """

    def perform(self) -> list[Action]:
        """
        Performs the preprocessing.

        :return: Action to analyse resulting source.
        """
        arguments: list[str] = []
        inclusion_dirs: set[Path] = set()
        for prereq in self._prereqs:
            if isinstance(prereq, InclusionPrerequisite):
                inclusion_dirs.add(self._database.inclusions[prereq.filename].parent)
        for directory in inclusion_dirs:
            arguments.append("-I" + str(directory))

        self.destination_file.parent.mkdir(parents=True, exist_ok=True)
        self.run_subprocess(arguments)
        return [AnalyseFortran(self.destination_file, self._database)]


class AnalyseFortran(Action):
    """
    Analyses Fortran source for dependency information.
    """

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
        """
        :param source: Fortran source to analyse.
        :param database: Build system state and configuration.
        """
        super().__init__(str(source))
        self._source = source
        self._database = database

    @property
    def source(self) -> Path:
        """
        :return: Fortran source file.
        """
        return self._source

    def __str__(self) -> str:
        return "Analyse: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determines prerequisites for analysis.

        :return: Source file must exist.
        """
        return [FilePrerequisite(self._source)]

    def perform(self) -> list[Action]:
        """
        Perform analyses.

        :return: If a ``program`` is discovered, A task to resolve it.
        """
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
                    if open_mp and not self._database.build_config["use_open_mp"]:
                        continue

                    if name in self._database.build_config["fc_ignore_modules"]:
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
    """
    Resolves list of modules making up a program.
    """

    def __init__(self, name: str, database: Database):
        """
        :param name: Program name.
        :param database: Build system state and configuration.
        """
        super().__init__(name)
        self._name = name
        self._database = database

        self._modules: set[str] = set()
        self._units = {name}

    def __str__(self) -> str:
        return f"DetermineProgram '{self._name}': {len(self._units)}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determine prerequisites.

        .. Todo:: Can (and should) this be dynamic based on the current state
                  of the scan?
        """
        return [AnalysedPrerequisite(self._name, self._database)]

    def perform(self) -> list[Action]:
        """
        Performs an iteration of resolving the program.

        Each time it is run this action chases as many prerequisites as it can
        through the tree of analysed source. Any unresolved dependencies are
        noted for next time and the action resubmits itself to the work queue.

        :return: For each prerequisite discovered a "compile" action is
                 returned. Additionally, when every prerequisite has been
                 determined a "link" action is returned, otherwise the action
                 returns itself.
        """
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


class CompileFortran(SubprocessAction):
    """
    Compiles Fortran source to object and module file.
    """

    def __init__(
        self,
        source: Path,
        prerequisites: Iterable[PrerequisiteInfo],
        database: Database,
    ):
        """
        :param source: Fortran source file.
        :param prerequisites: Dependencies needed to compile this file.
        :param database: Build system state and configuration.
        """
        self._source = source
        self._prerequisites = set(prerequisites)
        self._database = database

        # Todo: Hardwired assumption on workspace layout
        extra_arguments: list[str] = []
        branch_path = self._source.relative_to(
            self._database.script_config["paths"]["build_dir"]
        )
        for case, tags in self._database.build_config["tag_dirs"].items():
            if branch_path.is_relative_to(case):
                for tag in tags:
                    extra_arguments.extend(
                        self._database.build_config["build_tags"][tag]
                    )
        mp_get_logger().debug("Special arguments: " + ", ".join(extra_arguments))

        # Todo: Hardwired arguments
        arguments = [
            "-c",
            "-J",
            str(self._database.script_config["paths"]["module_dir"]),
            "-fopenmp",
            "-std=f2008",
            "-ffree-line-length-none",
        ]

        for arg in os_environ["FFLAGS"].split():
            arguments.append(arg)

        arguments.extend(extra_arguments)
        arguments.append("-fallow-argument-mismatch")

        destination = self._source.with_suffix(".o")
        arguments.extend([str(self._source), "-o", str(destination)])

        exe = Path("mpif90")
        super().__init__(exe, arguments)

    def __str__(self) -> str:
        return "Compile: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets prerequisite rules.

        Anything referred to be ``use`` statement generates a requirement on a
        module file. Symbols declared ``external`` are ignored as the compile
        takes it on trust that the linker will sort these out. The same is true
        for UM style ``depends-on`` comments.

        :return: Collection of prerequisite rules.
        """
        prereqs: list[Prerequisite] = []
        for symbol in self._prerequisites:
            if symbol.nature == PrerequisiteType.USE:
                name = Path(symbol.name).with_suffix(".mod").name
                module_file = self._database.script_config["paths"]["module_dir"] / name
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
        """
        Performs the compilation.

        .. Todo:: Hardwired assumption on workspace layout.

        :return: Error if the compilation failed.
        """
        self.run_subprocess()
        return []


class LinkFortran(SubprocessAction):
    """
    Uses Fortran compiler to link objects.
    """

    def __init__(self, program: str, modules: set[str], database: Database):
        """
        :param program: Name of resulting executable.
        :param modules: Collection of modules making up program.
        :param database: Build system state and configuration.
        """
        self._program = program
        self._modules = modules
        self._database = database

        dest = self._database.script_config["paths"]["bin_dir"] / self._program
        arguments = ["-o", dest, "-fopenmp"]

        self._library_args: list[str] = []
        for package in self._database.build_config["packages"]:
            for arg in package.link_arguments:
                if isinstance(arg, LinkerPath):
                    self._library_args.append("-L" + str(arg.path))

                    # Todo: This needs to be optional, for cases where we want
                    #       pure dynamic linkage.
                    #
                    self._library_args.append("-Wl,-rpath=" + str(arg.path))
                elif isinstance(arg, LibraryName):
                    self._library_args.append("-l" + arg.name)
                else:
                    raise RuntimeError("Unrecognised linker argument: " + str(arg))

        exe = Path("mpif90")
        super().__init__(exe, arguments)

    def __str__(self) -> str:
        return "Link: " + self._program

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets list of prerequisite rules.

        The link depends on a set of modules. Those which have been seen by the
        analyser create a prerequisite on the object file. Those which have not
        create a prerequisite on the analysis.

        :return: Collection of prerequisite rules.
        """
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
        """
        Perform the link action.

        :return: Error result if the linker failed.
        """
        objects: set[Path] = set()
        for module in self._modules:
            object_file = self._database.symbol_table[module].source_file.with_suffix(
                ".o"
            )
            objects.add(object_file)

        arguments: list[str] = []
        for object_file in objects:
            arguments.append(str(object_file))
        arguments.extend(self._library_args)

        self.run_subprocess(arguments)
        return []

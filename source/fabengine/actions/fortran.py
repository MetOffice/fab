from __future__ import annotations

from abc import ABC
from collections.abc import Generator, Iterable
from enum import Enum, auto
from os import environ as os_environ
from pathlib import Path
from re import IGNORECASE
from re import compile as re_compile

from fabengine.actions import (
    Action,
    Prerequisite,
    SubprocessAction,
    TwoPartPath,
)
from fabengine.actions.file import MapFile
from fabengine.artefact_store import ENCODING_META, Artefact, ArtefactPath
from fabengine.cui.status import set_ps_name
from fabengine.database import (
    Database,
    PrerequisiteInfo,
    PrerequisiteType,
    SymbolInfo,
    SymbolType,
)
from fabengine.logserver import make_logger
from fabengine.package import LibraryName, LinkerPath
from fabengine.prerequisite import (
    AnalysedPrerequisite,
    ArtefactPrerequisite,
    RealFilePrerequisite,
)


class MapFortran(MapFile):
    """
    Maps Fortran source into the virtual filesystem.
    """

    def __init__(
        self,
        real_file: TwoPartPath,
        encoding: str,
        database: Database,
        tag: str | None,
    ):
        super().__init__(real_file, database, tag)
        self._encoding = encoding

    def __str__(self) -> str:
        return f"Map Fortran: {self.real_file}"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [RealFilePrerequisite(self.real_path)]

    def perform(self) -> list[Action]:
        """
        Performs the mapping.

        :return: An AnalyseFortran object for the new file.
        """
        actions = super().perform()
        actions.append(AnalyseFortran(self.artefact_path, self._database))

        artefact = Artefact(self.artefact_path, self.real_path)
        artefact.set_meta(ENCODING_META, self._encoding)
        self._database.artefact_store.set_artefact(artefact)

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
        real_file: TwoPartPath,
        project: str,
        encoding: str,
        database: Database,
        macros: dict[str, str],
        force_include_dir: list[Path],
        kind="Fortran",
    ):
        """
        :param real_file: Source file as root and branch.
        :param project: Name under which to collect source in workspace.
        :param database: Build system state and configuration.
        :param macros: Additional macros to use with this preprocess.
        """
        self._real_file = real_file
        self._project = project
        self._encoding = encoding
        self._database = database
        self._macros = macros
        self._force_include_dir = force_include_dir
        self._kind = kind

        suffix = self._real_file.branch.suffix.lower()
        filename = self._real_file.branch.with_suffix(suffix)
        self._destination_path = ArtefactPath(self._project / filename)

        # Todo: Hardwired command
        arguments: list[str | Path] = ["-traditional-cpp", "-P"]

        for name, value in self._database.configuration["fpp_definitions"].items():
            arguments.append(f"-D{name}={value}")

        for name, value in self._macros.items():
            arguments.append(f"-D{name}={value}")

        super().__init__(Path("cpp"), arguments)

    def __str__(self) -> str:
        return f"Preprocess {self._kind} <({self._project}) {self._real_file.branch}>"

    @property
    def source_file(self) -> Path:
        """
        :return: Real path to source file.
        """
        return self._real_file.full

    @property
    def destination_file(self) -> ArtefactPath:
        """
        :return: Virtual path to destination file.
        """
        return self._destination_path

    def prerequisites(self) -> Iterable[Prerequisite]:
        return [RealFilePrerequisite(self._real_file.full)]

    def preprocess_file(
        self, additional_arguments: list[str | Path] | None = None
    ) -> None:
        """
        Performs the preprocessing.

        :return: An ActionResult if the preprocessor fails.
        """
        artefact = self._database.artefact_store.get_artefact(self.destination_file)
        artefact.set_meta(ENCODING_META, self._encoding)
        self._database.artefact_store.set_artefact(artefact)

        arguments: list[str | Path] = additional_arguments or []

        for path in self._force_include_dir:
            arguments.append(f"-I{path}")

        arguments.append(self.source_file)
        arguments.append(artefact.real_filename)

        self.run_subprocess(additional_arguments=arguments)


class PreprocessFortranAction(PreprocessFortranBase):
    """
    Preprocesses Fortran source.
    """

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Performs the preprocessing.

        :return: Action to analyse resulting source.
        """
        super().preprocess_file()
        return [AnalyseFortran(self.destination_file, self._database)]


# Todo: This pattern does not handle exclamation marks in quotes.
_COMMENT_PATTERN = re_compile(r"(.*?)\s*!(?!\$|\s*DEPENDS\s*ON\s*:\s*).*$", IGNORECASE)
_CONTINUATION_PATTERN = re_compile(r"\s*&\s*(.*)")
_CONTINUE_PATTERN = re_compile(r"\s*(.*?)\s*&\s*$")


def normalise_source(artefact: Artefact) -> Generator[str, None, None]:
    try:
        encoding = artefact.get_meta(ENCODING_META)
    except KeyError:
        encoding = "utf8"
    line_buffer = ""
    with artefact.real_filename.open("rt", encoding=encoding) as stream:
        for line in stream:
            match = _COMMENT_PATTERN.match(line)
            if match:  # Remove comments
                line = match.group(1)

            if not line.strip():  # Ignore blank lines
                continue

            match = _CONTINUATION_PATTERN.match(line)
            if match:  # Remove leading ampersand
                line = match.group(1)

            match = _CONTINUE_PATTERN.match(line)
            if match:  # Buffer continuing lines
                if line_buffer:
                    line_buffer += " " + match.group(1)
                else:
                    line_buffer = match.group(1)
            else:  # No further continuation
                if line_buffer:
                    yield line_buffer + " " + line.strip()
                    line_buffer = ""
                else:
                    yield line.rstrip()


class AnalyseFortran(Action):
    """
    Analyses Fortran source for dependency information.
    """

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

    def __init__(self, source: ArtefactPath, database: Database):
        """
        :param source: Fortran source to analyse.
        :param database: Build system state and configuration.
        """
        super().__init__(str(source))
        self._source = source
        self._database = database

    @property
    def source(self) -> ArtefactPath:
        """
        :return: Fortran source file.
        """
        return self._source

    def __str__(self) -> str:
        return f"Analyse: <{self._source}>"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determines prerequisites for analysis.

        :return: Source file must exist.
        """
        return [ArtefactPrerequisite(self._source, self._database)]

    _UM_DEPENDS_ON_PATTERN = re_compile(r"\s*!\s*DEPENDS\s*ON\s*:\s*(\w+)", IGNORECASE)

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform analyses.

        :return: If a ``program`` is discovered, A task to resolve it.
        """
        logger = make_logger("system")

        actions: list[Action] = []

        artefact = self._database.artefact_store.get_artefact(self._source)

        unit_prereqs: dict[str, PrerequisiteInfo] = {}
        current_unit: str | None = None
        contains_units: list[str] = []

        class State(Enum):
            SEEKING = auto()
            IN_UNIT = auto()

        state = State.SEEKING
        for line in normalise_source(artefact):
            logger.debug(f"{state} - {line}")
            if state == State.SEEKING:
                match = self._UNIT_PATTERN.match(line)
                if match:
                    unit = match.group(1).lower()
                    name = match.group(2).lower()
                    logger.info("Found unit: " + name)

                    if name in self._database.symbol_table:
                        raise RuntimeError(
                            f"Duplicate unit '{name}' "
                            f"found in {self._source.name}. Previously seen in "
                            + self._database.symbol_table[name].source_file.name
                        )

                    info = SymbolInfo(name, SymbolType[unit.upper()], self._source)
                    self._database.symbol_table[name] = info

                    current_unit = name
                    contains_units.append(name)

                    if unit == "program":
                        actions.append(DetermineFortranProgram(name, self._database))

                    state = State.IN_UNIT

            elif state == State.IN_UNIT:
                match = self._TYPE_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()
                    info = SymbolInfo(name, SymbolType.TYPE, self._source)
                    self._database.symbol_table[name] = info
                    logger.info("Found type: " + name)
                    continue

                match = self._PUBLIC_PATTERN.match(line)
                if match:
                    for symbol in match.group(2).lower().split(","):
                        symbol = symbol.strip()
                        info = SymbolInfo(symbol, SymbolType.PROCEDURE, self._source)
                        self._database.symbol_table[symbol] = info
                        logger.info("Found public: " + symbol)
                        continue

                match = self._USE_PATTERN.match(line)
                if match:
                    name = match.group(2).lower()
                    open_mp = match.group(1) or ""
                    open_mp = "OpenMP " if open_mp.strip() else ""
                    if open_mp and not self._database.configuration["use_open_mp"]:
                        continue

                    if name in self._database.configuration["fc_ignore_modules"]:
                        continue

                    # Todo: We need to reject internal dependencies. This
                    #       approach only works backwards. i.e. only detects
                    #       references to units already seen.
                    #
                    if name not in unit_prereqs and name not in contains_units:
                        unit_prereqs[name] = PrerequisiteInfo(
                            name, PrerequisiteType.USE
                        )
                    continue

                match = self._EXTERNAL_PATTERN.match(line)
                if match:
                    name = match.group(1).lower()
                    if name not in unit_prereqs:
                        logger.info("Found external: " + name)
                        unit_prereqs[name] = PrerequisiteInfo(
                            name, PrerequisiteType.EXTERNAL
                        )
                    continue

                match = self._UM_DEPENDS_ON_PATTERN.match(line)
                if match:
                    symbol = match.group(1).lower()
                    if symbol not in unit_prereqs:
                        logger.info("Found UM dependency comment: " + symbol)
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
                        logger.info("End of unit: " + name)

                        self._database.prerequisites[current_unit] = list(
                            unit_prereqs.values()
                        )

                        current_unit = None

                        state = State.SEEKING
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

    def __eq__(self, other: object) -> bool:
        # Because DetermineFortranProgram will be compared against other
        # Action objects, it can't simply fail if the other is of different
        # type.
        #
        assert isinstance(other, Action)
        if isinstance(other, DetermineFortranProgram):
            return self._name == other._name and self._database == other._database
        else:
            return False

    def __repr__(self) -> str:
        return f"DetermineFortranProgram({self._name}, {self._database})"

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
        logger = make_logger("system")
        actions: list[Action] = []

        working_units = self._units
        self._units = set()
        while working_units:
            unit_name = working_units.pop()
            logger.debug("Considering: " + unit_name)
            if unit_name in self._database.prerequisites:
                logger.debug(f"Modules: {self._modules}")
                if unit_name in self._modules:
                    logger.debug("Is module: " + unit_name)
                    continue
                self._modules.add(unit_name)

                # Todo: When multiple executables share modules (which happens by
                #       definition with unit tests) each "DetermineProgram" task
                #       will enqueue a compile action. These duplicate compile
                #       actions then race each other causing unpredictable
                #       and inexplicable failures.
                #
                source = self._database.symbol_table[unit_name].source_file
                if source not in self._database.compiles_enqueued:
                    self._database.compiles_enqueued.append(source)
                    actions.append(
                        CompileFortran(
                            source,
                            self._database.prerequisites[unit_name],
                            self._database,
                        )
                    )

                # We want to catch as many prerequisites as possible per
                # pass, so they are added to the current list rather than
                # the future list.
                #
                for prereq in self._database.prerequisites[unit_name]:
                    working_units.add(prereq.name)

                # Deal with any hand specified dependencies:
                #
                for prereq in self._database.configuration["forced_prerequisites"].get(
                    unit_name, []
                ):
                    working_units.add(prereq)
            else:  # Unit has not yet been analysed
                logger.debug("Not yet seen: " + unit_name)
                self._units.add(unit_name)

        if len(self._units) == 0:
            actions.append(LinkFortran(self._name, self._modules, self._database))
        else:
            logger.debug(f"Missing: {', '.join(self._units)}")
            actions.append(self)
        return actions


class CompileFortran(SubprocessAction):
    """
    Compiles Fortran source to object and module file.
    """

    def __init__(
        self,
        source: ArtefactPath,
        prerequisites: Iterable[PrerequisiteInfo],
        database: Database,
        syntax_only: bool = True,
    ):
        """
        :param source: Fortran source file.
        :param prerequisites: Dependencies needed to compile this file.
        :param database: Build system state and configuration.
        :param syntax_only: Optionally compile to generate the module files.
        """
        # Todo: Shouldn't this action know it's own prerequisites?
        #
        self._source = source
        self._prerequisites = set(prerequisites)
        self._database = database
        self._syntax_only = syntax_only

        extra_arguments: list[str] = []
        for case, tags in self._database.configuration["tag_dirs"].items():
            if self._source.is_relative_to(case):
                for tag in tags:
                    extra_arguments.extend(
                        self._database.configuration["build_tags"][tag]
                    )
        make_logger("system").debug("Special arguments: " + ", ".join(extra_arguments))

        self._full_module_dir = self._database.configuration["paths"]["module_dir"]
        self._full_module_dir.mkdir(parents=True, exist_ok=True)
        # Todo: Hardwired arguments
        arguments = [
            "-c",
            "-J",
            self._full_module_dir,
            "-fopenmp",
            "-std=f2008",
            "-ffree-line-length-none",
        ]

        if self.first_pass:
            arguments.append("-fsyntax-only")

        arguments.extend(os_environ["FFLAGS"].split())
        arguments.extend(extra_arguments)

        arguments.extend(
            [
                self._database.artefact_store.get_artefact(self._source).real_filename,
                "-o",
                self._database.artefact_store.get_artefact(
                    self._source.with_suffix(".o")
                ).real_filename,
            ]
        )

        exe = Path("mpif90")
        super().__init__(exe, arguments)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Action)
        if isinstance(other, CompileFortran):
            return (
                self._source == other._source
                and self._prerequisites == other._prerequisites
            )
        else:
            return False

    def __repr__(self) -> str:
        return f"CompileFortran({self._source}, {self._prerequisites})"

    def __str__(self) -> str:
        return f"Compile: <{self._source}>"

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
                module_file = self._full_module_dir / name
                prereqs.append(RealFilePrerequisite(module_file))
            elif symbol.nature == PrerequisiteType.EXTERNAL:
                pass  # The compiler doesn't interrogate externals
            elif symbol.nature == PrerequisiteType.UM:
                pass  # Nor does it interrogate UM-era dependency comments
            elif symbol.nature == PrerequisiteType.FORCED:
                pass  # Nor does it interrogate forced dependencies
            else:
                raise RuntimeError(
                    f"Unrecognised prerequisite type '{symbol.nature}'of {symbol.name}."
                )
        return prereqs

    @set_ps_name
    def perform(self) -> Iterable[Action]:
        """
        Performs the compilation.

        .. Todo:: Hardwired assumption on workspace layout.

        :return: Error if the compilation failed.
        """
        self.run_subprocess()

        if self.first_pass:
            return [CompileFortran(self._source, [], self._database, False)]
        return []

    @property
    def first_pass(self):
        """If two pass compiles are enabled and this is the first pass."""
        return (
            self._database.configuration.get("two_pass_compilation", False)
            and self._syntax_only
        )


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

        # Todo: Obviously, this action should not be choosing destination like
        #       this. However, communicating it is made tricky by where the
        #       knowledge is. For instance, the pFUnit actions know where test
        #       executables should end up.
        #
        #       Maybe Creating the link object at the same time as the source
        #       is created and passing it along for use later?
        #
        #       This may link to the problem that unit testing has to make
        #       assumptions of where the executable will end up. See pfunit.py.
        #
        if self._program.endswith("_test_prog"):
            self._exe_file = (
                self._database.configuration["paths"]["work_dir"]
                / "unit-test"
                / self._program
            )
        else:
            self._exe_file = (
                self._database.configuration["paths"]["bin_dir"] / self._program
            )
        self._exe_file.parent.mkdir(parents=True, exist_ok=True)

        arguments = ["-fopenmp", "-o", self._exe_file]

        # Todo: Support for pure static linkage?

        self._library_args: list[str] = []
        for package in self._database.configuration["packages"].values():
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
                    raise TypeError("Unrecognised linker argument: " + str(arg))

        exe = Path("mpif90")
        super().__init__(exe, arguments)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Action)
        if isinstance(other, LinkFortran):
            return self._program == other._program and self._modules == other._modules
        else:
            return False

    def __repr__(self) -> str:
        return f"LinkFortran({self._program}, {self._modules})"

    def __str__(self) -> str:
        return "Link: " + self._program

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets list of prerequisite rules.

        The link depends on a set of modules. Those which have been seen by the
        analyser create a prerequisite on the object file. Those which have
        not, create a prerequisite on the analysis.

        :return: Collection of prerequisite rules.
        """
        prereqs: list[Prerequisite] = []
        for module in self._modules:
            if module in self._database.symbol_table:
                object_file = self._database.symbol_table[
                    module
                ].source_file.with_suffix(".o")
                prereqs.append(ArtefactPrerequisite(object_file, self._database))
            else:  # Module has not yet been analysed
                prereqs.append(AnalysedPrerequisite(module, self._database))
        return prereqs

    @set_ps_name
    def perform(self) -> list[Action]:
        """
        Perform the link action.

        :return: Error result if the linker failed.
        """
        objects: set[Path] = set()
        for module in self._modules:
            virtual_file = self._database.symbol_table[module].source_file.with_suffix(
                ".o"
            )
            artefact = self._database.artefact_store.get_artefact(virtual_file)
            objects.add(artefact.real_filename)

        arguments: list[str | Path] = list(objects)
        arguments.extend(self._library_args)

        self.run_subprocess(additional_arguments=arguments)

        # todo: what if there is a pre-existing executable with the
        # same name?
        if self._exe_file.exists():
            self._database.artefact_store.map_file(
                self._exe_file,
                Path("bin") / self._exe_file.name,
                binary_target=True,
            )

        return []

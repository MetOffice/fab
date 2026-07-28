from __future__ import annotations

from collections.abc import Generator, Iterable
from enum import Enum, auto
from multiprocessing import get_logger as mp_get_logger
from pathlib import Path
from re import IGNORECASE
from re import compile as re_compile

from fabengine.actions import Action, Prerequisite, SubprocessAction
from fabengine.actions.file import MapFile
from fabengine.database import ArtefactPath, Database
from fabengine.prerequisite import ArtefactPrerequisite, RealFilePrerequisite


class MapC(MapFile):
    """
    Copies C source into workspace.
    """

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determines prerequisites for compilation.

        :return: Source file must exist.
        """
        return [RealFilePrerequisite(self.real_path)]

    def perform(self) -> list[Action]:
        """
        Performs the copy.

        :return: An AnalyseC object for the new file.
        """

        actions = super().perform()
        actions.append(AnalyseC(self.artefact_path, self._database))
        return actions


class AnalyseC(Action):
    """
    Analyses C source for information about dependencies
    and whether it contains a main program.
    """

    _SINGLE_COMMENT_PATTERN = re_compile(r"^(.*?)\/\/.*$", IGNORECASE)
    _BEGIN_COMMENT_PATTERN = re_compile(r"^(.*?)\/\*.*$", IGNORECASE)
    _END_COMMENT_PATTERN = re_compile(r"^.*\*\/(.*?)$", IGNORECASE)
    _INCLUDE_PATTERN = re_compile(
        r"^\s*#include\s+\"(\w|.+)\".*$", IGNORECASE
    )  # only matching local, not system, includes
    _MAIN_PATTERN = re_compile(r"^\s*(?:(?:int|void)\s+)?main\s*\(.*\).*$", IGNORECASE)

    class AnalysisMode(Enum):
        SEEKING = auto()
        IN_COMMENT = auto()

    def __init__(self, source: ArtefactPath, database: Database):
        """
        :param source: C source to analyse.
        :param database: Build system state and configuration.
        """
        super().__init__(str(source))
        self._source = source
        self._database = database

    def __str__(self) -> str:
        return "Analyse: " + self._source.name

    @staticmethod
    def _normalise_source(source: Path) -> Generator[str, None, None]:
        """
        Normalises C source by removing comments and blank lines.
        """

        mode = AnalyseC.AnalysisMode.SEEKING

        for line in source.read_text().splitlines():
            if mode == AnalyseC.AnalysisMode.IN_COMMENT:
                # we are in a comment, so look for the end of the comment
                match = AnalyseC._END_COMMENT_PATTERN.match(line)
                if match:
                    # found end of comment, switch back to seeking mode and check if there is any code after the comment ends
                    mode = AnalyseC.AnalysisMode.SEEKING
                    after_comment = match.group(1).strip()
                    if after_comment:
                        yield after_comment

            elif mode == AnalyseC.AnalysisMode.SEEKING:
                # we are seeking, so look for the start of a comment
                match = AnalyseC._BEGIN_COMMENT_PATTERN.match(line)
                if match:
                    # found start of comment, switch to in_comment mode and check if there is any code before the comment starts
                    mode = AnalyseC.AnalysisMode.IN_COMMENT
                    before_comment = match.group(1).strip()
                    if before_comment:
                        yield before_comment
                    # We need to check this comment block isn't closed on the same line
                    match = AnalyseC._END_COMMENT_PATTERN.match(line)
                    if match:
                        # found end of comment, switch back to seeking mode and check if
                        # there is any code after the comment ends
                        mode = AnalyseC.AnalysisMode.SEEKING
                        after_comment = match.group(1).strip()
                        if after_comment:
                            yield after_comment

                else:
                    # we are seeking and did not find the start of a comment, so look for a single-line comment
                    match = AnalyseC._SINGLE_COMMENT_PATTERN.match(line)
                    if match:
                        # found a single-line comment so check if there is any code before the comment starts
                        before_comment = match.group(1).strip()
                        if before_comment:
                            yield before_comment
                    else:
                        # now we are sure we are not dealing w/ comments, so we can analyse the line as normal
                        stripped_line = line.strip()
                        if stripped_line:
                            yield stripped_line

            else:
                raise RuntimeError("Unhandled AnalysisMode: " + str(mode))

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determines prerequisites for analysis.

        :return: Source file must exist.
        """
        return [ArtefactPrerequisite(self._source, self._database)]

    def perform(self) -> list[Action]:
        """
        Perform analyses.

        :return: Every source file must be return a CompileC action, and those with a main program must also return a LinkC action.
        """

        logger = mp_get_logger()
        logger.debug(f"AnalyseC: {self._source.name}")

        source_basename = self._source.stem

        actions: list[Action] = []
        linker_prerequisites: list[ArtefactPrerequisite] = []

        found_main = False

        for normalised_line in self._normalise_source(
            self._database.artefact_store.get_artefact(self._source)
        ):
            # (comments and blank lines have already been removed, so we can just search for includes and main programs without worrying about comment syntax)

            match = self._MAIN_PATTERN.match(normalised_line)
            if match:
                # found main program
                logger.debug(f"AnalyseC found a main program in {self._source.name}")
                found_main = True
                continue

            match = self._INCLUDE_PATTERN.match(normalised_line)
            if match:
                # found an include, so add a prerequisite for the included file (so long as it isn't a self-include)
                included_file = match.group(1)
                included_file_basename = included_file.rpartition(".")[0]
                if included_file_basename != source_basename:
                    logger.debug(
                        f"AnalyseC found a dependency: {included_file} in {self._source.name}"
                    )
                    linker_prerequisites.append(
                        ArtefactPrerequisite(
                            ArtefactPath(included_file_basename + ".o"), self._database
                        )
                    )
                continue

        # all source files need to be compiled
        actions.append(CompileC(self._source, self.prerequisites(), self._database))
        if found_main:
            # those source files w/ a main program, also need to be linked into an executable
            # Prerequisites are sorted to avoid non-deterministic behaviour upsetting testing.
            actions.append(
                LinkC(self._source, sorted(linker_prerequisites), self._database)
            )

        return actions


class CompileC(SubprocessAction):
    """
    Compiles C source to object file.
    """

    _COMPILER = "gcc"

    def __init__(
        self,
        source: Path,
        prerequisites: Iterable[Prerequisite],
        database: Database,
    ):
        """
        :param source: C source file.
        :param prerequisites: Dependencies needed to compile this file.
        :param database: Build system state and configuration.
        """
        self._source = source
        self._prerequisites = set(prerequisites)
        self._database = database

        arguments = []
        destination = self._source.with_suffix(".o")
        arguments.extend(["-c", str(self._source), "-o", str(destination)])

        exe = Path(self._COMPILER)
        super().__init__(exe, arguments)

    def __str__(self) -> str:
        return "Compile: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Determines prerequisites for compilation.

        Unlike Fortran, C does not have an explicit module system.
        Instead, dependencies are determined by the presence of "#include" directives.
        Header files will already have been imported as part of the ImportC Action.
        And, the compiler automatically handles these dependencies so no explicit prerequisite rules are needed.
        """
        prereqs: list[Prerequisite] = []
        return prereqs

    def perform(self) -> Iterable[Action]:
        """
        Performs the compilation.

        :return: Error if the compilation failed.
        """
        logger = mp_get_logger()
        logger.debug(f"CompileC: {self._source.name}")

        self.run_subprocess()
        return []


class LinkC(SubprocessAction):
    """
    Uses C compiler to link object into executable.
    """

    _LINKER = "gcc"

    def __init__(
        self,
        source: Path,
        prerequisites: Iterable[ArtefactPrerequisite],
        database: Database,
    ):
        """
        :param source: C source file containing the main program. The name of the executable will be derived from this.
        :param prerequisites: Dependencies needed to link this file.
        :param database: Build system state and configuration.
        """
        self._source = source
        self._prerequisites = set(prerequisites)
        self._database = database

        self._object_file = ArtefactPath(self._source.with_suffix(".o"))
        self._prerequisites.add(ArtefactPrerequisite(self._object_file, self._database))

        dest = self._database.configuration["paths"]["bin_dir"] / self._source.stem
        arguments = [
            *[
                prerequisite.filename.real_filename
                for prerequisite in sorted(self._prerequisites)
            ],
            "-o",
            dest,
        ]

        exe = Path(self._LINKER)
        super().__init__(exe, arguments)

    def __str__(self) -> str:
        return "Link: " + self._source.name

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        Gets list of prerequisite rules.

        The linker depends on having already built all dependent object files.

        :return: Collection of prerequisite rules.
        """
        prereqs = self._prerequisites
        prereqs.add(ArtefactPrerequisite(self._object_file, self._database))
        return prereqs

    def perform(self) -> list[Action]:
        """
        Perform the link action.

        :return: Error result if the linker failed.
        """
        logger = mp_get_logger()
        logger.debug(f"LinkC: {self._source.name}")

        self.run_subprocess()
        return []

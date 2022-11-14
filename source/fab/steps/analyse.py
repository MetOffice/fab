##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fab parses each C and Fortran file into an :class:`~fab.steps.dep_tree.AnalysedFile` object
which contains the symbol definitions and dependencies for that file.

From this set of analysed files, Fab builds a symbol table mapping symbols to their containing files.

Fab uses the symbol table to turn symbol dependencies into file dependencies (stored in the AnalysedFile objects).
This gives us a file dependency tree for the entire project source. The data structure is simple,
just a dict of *<source path>: <analysed file>*, where the analysed files' dependencies are other dict keys.

If we're building a library, that's the end of the analysis process as we'll compile the entire project source.
If we're building one or more executables, which happens when we use the `root_symbol` argument,
Fab will extract a subtree from the entire dependency tree for each root symbol we specify.

Finally, the resulting artefact collection is a dict of these subtrees (*"build trees"*),
mapping *<root symbol>: <build tree>*.
When building a library, there will be a single tree with a root symbol of `None`.

Addendum: The language parsers Fab uses are unable to detect some kinds of dependency.
For example, fparser can't currently identify a call statement in a one-line if statement.
We can tell Fab that certain symbols *should have been included* in the build tree
using the `unreferenced_deps` argument.
For every symbol we provide, its source file *and dependencies* will be added to the build trees.

Sometimes a language parser will crash while parsing a *valid* source file, even though the compiler
can compile the file perfectly well. In this case we can give Fab the analysis results it should have made
by passing AnalysedFile objects into the `special_measure_analysis_results` argument.
You'll have to manually read the file to determine which symbol definitions and dependencies it contains.

"""

import logging
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Iterable, Set, Optional, Union

from fab.constants import BUILD_TREES
from fab.dep_tree import AnalysedFile, add_mo_commented_file_deps, extract_sub_tree, \
    validate_dependencies
from fab.steps import Step
from fab.tasks.c import CAnalyser
from fab.tasks.fortran import FortranAnalyser
from fab.util import TimerLogger, by_type
from fab.artefacts import ArtefactsGetter, CollectionConcat, SuffixFilter

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = CollectionConcat([
    SuffixFilter('all_source', '.f90'),
    'preprocessed_c',
    'preprocessed_fortran',

    # todo: this is lfric stuff so might be better placed with the lfric run configs
    SuffixFilter('psyclone_output', '.f90'),
    'preprocessed_psyclone',
    'configurator_output',
])


# todo: split out c and fortran? this class is still a bit big
# This has all been done as a single step, for now, because we don't have a simple mp pattern
# (i.e we don't have a list of artefacts and a function to feed them through).
class Analyse(Step):
    """
    Produce one or more build trees by analysing source code dependencies.

    The resulting artefact collection is a mapping from root symbol to build tree.
    The name of this artefact collection is taken from :py:const:`fab.constants.BUILD_TREES`.

    """
    # todo: allow the user to specify a different output artefact collection name?
    def __init__(self,
                 source: Optional[ArtefactsGetter] = None,
                 root_symbol: Optional[Union[str, List[str]]] = None,  # todo: iterable is more correct
                 std: str = "f2008",
                 special_measure_analysis_results: Optional[List[AnalysedFile]] = None,
                 unreferenced_deps: Optional[Iterable[str]] = None,
                 ignore_mod_deps: Optional[Iterable[str]] = None,
                 name='analyser'):
        """
        If no artefact getter is specified in *source*, a default is used which provides input files
        from multiple artefact collections, including the default C and Fortran preprocessor outputs
        and any source files with a 'little' *.f90* extension.

        A build tree is produced for every root symbol specified in *root_symbol*, which can be a string or list of.
        This is how we create executable files. If no root symbol is specified, a single tree of the entire source
        is produced (with a root symbol of `None`). This is how we create shared and static libraries.

        :param source:
            An :class:`~fab.util.ArtefactsGetter` to get the source files.
        :param root_symbol:
            When building an executable, provide the Fortran Program name(s), or 'main' for C.
            If None, build tree extraction will not be performed and the entire source will be used
            as the build tree - for building a shared or static library.
        :param std:
            The fortran standard, passed through to fparser2. Defaults to 'f2008'.
        :param special_measure_analysis_results:
            When fparser2 cannot parse a "valid" Fortran file,
            we can manually provide the expected analysis results with this argument.
            Only the symbol definitions and dependencies need be provided.
        :param unreferenced_deps:
            A list of symbols which are needed for the build, but which cannot be automatically determined by Fab.
            For example, functions that are called in a one-line if statement.
            Assuming the files containing these symbols are present and analysed,
            those files and all their dependencies will be added to the build tree(s).
        :param ignore_mod_deps:
            Third party Fortran module names to be ignored.
        :param name:
            Human friendly name for logger output, with sensible default.

        """

        # Note: a code smell?: we insist on the manual analysis results, special_measure_analysis_results,
        # arriving as a list not a set because we don't want to hash them yet,
        # because the files they refer to probably don't exist yet,
        # because we're just creating steps at this point, so there's been no grab...

        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.root_symbols: Optional[List[str]] = [root_symbol] if isinstance(root_symbol, str) else root_symbol
        self.special_measure_analysis_results: List[AnalysedFile] = list(special_measure_analysis_results or [])
        self.unreferenced_deps: List[str] = list(unreferenced_deps or [])

        # todo: these seem more like functions
        self.fortran_analyser = FortranAnalyser(std=std, ignore_mod_deps=ignore_mod_deps)
        self.c_analyser = CAnalyser()

    def run(self, artefact_store: Dict, config):
        """
        Creates the *build_trees* artefact from the files in `self.source_getter`.

        Does the following, in order:
            - Create a hash of every source file. Used to check if it's already been analysed.
            - Parse the C and Fortran files to find external symbol definitions and dependencies in each file.
                - Analysis results are stored in a csv as-we-go, so analysis can be resumed if interrupted.
            - Create a 'symbol table' recording which file each symbol is in.
            - Work out the file dependencies from the symbol dependencies.
                - At this point we have a source tree for the entire source.
            - (Optionally) Extract a sub tree for every root symbol, if provided. For building executables.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        :param artefact_store:
            Contains artefacts created by previous Steps, and where we add our new artefacts.
            This is where the given :class:`~fab.artefacts.ArtefactsGetter` finds the artefacts to process.
        :param config:
            The :class:`fab.build_config.BuildConfig` object where we can read settings
            such as the project workspace folder or the multiprocessing flag.

        """
        super().run(artefact_store, config)

        # todo: code smell - refactor (in another PR to keep things small)
        self.fortran_analyser._prebuild_folder = self._config.prebuild_folder
        self.c_analyser._prebuild_folder = self._config.prebuild_folder

        files: List[Path] = self.source_getter(artefact_store)
        analysed_files = self._parse_files(files=files)

        # add special measure symbols for files which could not be parsed
        if self.special_measure_analysis_results:
            warnings.warn("SPECIAL MEASURE: injecting user-defined analysis results")
            analysed_files.update(set(self.special_measure_analysis_results))

        project_source_tree, symbols = self._analyse_dependencies(analysed_files)

        # add the file dependencies for MO FCM's "DEPENDS ON:" commented file deps (being removed soon)
        with TimerLogger("adding MO FCM 'DEPENDS ON:' file dependency comments"):
            add_mo_commented_file_deps(project_source_tree)

        logger.info(f"source tree size {len(project_source_tree)}")

        # build tree extraction for executables.
        if self.root_symbols:
            build_trees = self._extract_build_trees(project_source_tree, symbols)
        else:
            build_trees = {None: project_source_tree}

        # throw in any extra source we need, which Fab can't automatically detect
        for build_tree in build_trees.values():
            self._add_unreferenced_deps(symbols, project_source_tree, build_tree)
            validate_dependencies(build_tree)

        artefact_store[BUILD_TREES] = build_trees

    def _analyse_dependencies(self, analysed_files: Iterable[AnalysedFile]):
        """
        Turn symbol deps into file deps and build a source dependency tree for the entire source.

        """
        with TimerLogger("converting symbol dependencies to file dependencies"):
            # map symbols to the files they're in
            symbols: Dict[str, Path] = self._gen_symbol_table(analysed_files)

            # fill in the file deps attribute in the analysed file objects
            self._gen_file_deps(analysed_files, symbols)

        source_tree: Dict[Path, AnalysedFile] = {a.fpath: a for a in analysed_files}
        return source_tree, symbols

    def _extract_build_trees(self, project_source_tree, symbols):
        """
        Find the subset of files needed to build each root symbol (executable).

        Assumes we have been given a root symbol(s) or we wouldn't have been called.
        Returns a build tree for every root symbol.

        """
        build_trees = {}
        for root in self.root_symbols:
            with TimerLogger(f"extracting build tree for root '{root}'"):
                build_tree = extract_sub_tree(project_source_tree, symbols[root], verbose=False)

            logger.info(f"target source tree size {len(build_tree)} (target '{symbols[root]}')")
            build_trees[root] = build_tree

        return build_trees

    def _parse_files(self, files: List[Path]) -> Set[AnalysedFile]:
        """
        Determine the symbols which are defined in, and used by, each file.

        Returns the analysed_fortran and analysed_c as lists of :class:`~fab.dep_tree.AnalysedFile`
        with no file dependencies, to be filled in later.

        """
        # fortran
        fortran_files = set(filter(lambda f: f.suffix == '.f90', files))
        with TimerLogger(f"analysing {len(fortran_files)} preprocessed fortran files"):
            fortran_results = self.run_mp(items=fortran_files, func=self.fortran_analyser.run)

        # c
        c_files = set(filter(lambda f: f.suffix == '.c', files))
        with TimerLogger(f"analysing {len(c_files)} preprocessed c files"):
            # The C analyser hangs with multiprocessing in Python 3.7!
            # Override the multiprocessing flag.
            no_multiprocessing = False
            if sys.version.startswith('3.7'):
                warnings.warn('Python 3.7 detected. Disabling multiprocessing for C analysis.')
                no_multiprocessing = True
            c_results = self.run_mp(items=c_files, func=self.c_analyser.run, no_multiprocessing=no_multiprocessing)

        # Check for parse errors but don't fail. The failed files might not be required.
        results = fortran_results + c_results
        exceptions = list(by_type(results, Exception))
        if exceptions:
            logger.error(f"{len(exceptions)} analysis errors")

        # warn about naughty fortran usage?
        if self.fortran_analyser.depends_on_comment_found:
            warnings.warn("deprecated 'DEPENDS ON:' comment found in fortran code")

        return set(by_type(results, AnalysedFile))

    def _gen_symbol_table(self, analysed_files: Iterable[AnalysedFile]) -> Dict[str, Path]:
        """
        Create a dictionary mapping symbol names to the files in which they appear.

        """
        symbols: Dict[str, Path] = dict()
        duplicates = []
        for analysed_file in analysed_files:
            for symbol_def in analysed_file.symbol_defs:
                # check for duplicates
                if symbol_def in symbols:
                    duplicates.append(ValueError(
                        f"duplicate symbol '{symbol_def}' defined in {analysed_file.fpath} "
                        f"already found in {symbols[symbol_def]}"))
                    continue
                symbols[symbol_def] = analysed_file.fpath

        if duplicates:
            # we don't break the build because these symbols might not be required to build the exe
            # todo: put a big warning at the end of the build?
            err_msg = "\n".join(map(str, duplicates))
            warnings.warn(f"Duplicates found while generating symbol table:\n{err_msg}")

        return symbols

    def _gen_file_deps(self, analysed_files: Iterable[AnalysedFile], symbols: Dict[str, Path]):
        """
        Use the symbol table to convert symbol dependencies into file dependencies.

        """
        deps_not_found = set()
        with TimerLogger("converting symbol to file deps"):
            for analysed_file in analysed_files:
                for symbol_dep in analysed_file.symbol_deps:
                    file_dep = symbols.get(symbol_dep)
                    # don't depend on oneself!
                    if file_dep == analysed_file.fpath:
                        continue
                    # warn of missing file
                    if not file_dep:
                        deps_not_found.add(symbol_dep)
                        logger.debug(f"not found {symbol_dep} for {analysed_file.fpath}")
                        continue
                    analysed_file.file_deps.add(file_dep)
        if deps_not_found:
            logger.info(f"{len(deps_not_found)} deps not found")

    def _add_unreferenced_deps(self, symbols: Dict[str, Path],
                               all_analysed_files: Dict[Path, AnalysedFile], build_tree: Dict[Path, AnalysedFile]):
        """
        Add files to the build tree.

        This is used for building Fortran code which Fab doesn't know is a dependency.

        """
        if not self.unreferenced_deps:
            return
        logger.info(f"Adding {len(self.unreferenced_deps or [])} unreferenced dependencies")

        for symbol_dep in self.unreferenced_deps:

            # what file is the symbol in?
            analysed_fpath = symbols.get(symbol_dep)
            if not analysed_fpath:
                warnings.warn(f"no file found for unreferenced dependency {symbol_dep}")
                continue
            analysed_file = all_analysed_files[analysed_fpath]

            # was it found and analysed?
            if not analysed_file:
                warnings.warn(f"couldn't find file for symbol dep '{symbol_dep}'")
                continue

            # is it already in the build tree?
            if analysed_file.fpath in build_tree:
                logger.info(f"file {analysed_file.fpath} for unreferenced dependency {symbol_dep} "
                            f"is already in the build tree")
                continue

            # add the file and it's file deps
            sub_tree = extract_sub_tree(source_tree=all_analysed_files, root=analysed_fpath)
            build_tree.update(sub_tree)

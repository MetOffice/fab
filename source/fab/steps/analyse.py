##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Fab parses each C and Fortran file into an :class:`~fab.steps.dep_tree.AnalysedDependent` object
which contains the symbol definitions and dependencies for that file.

From this set of analysed files, Fab builds a symbol table mapping symbols to their containing files.

Fab uses the symbol table to turn symbol dependencies into file dependencies (stored in the AnalysedDependent objects).
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
by passing FortranParserWorkaround objects into the `special_measure_analysis_results` argument.
You'll have to manually read the file to determine which symbol definitions and dependencies it contains.

"""
from itertools import chain
import logging
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Iterable, Set, Optional, Union

from fab import FabException
from fab.artefacts import ArtefactsGetter, ArtefactStore, CollectionConcat, SuffixFilter
from fab.constants import BUILD_TREES
from fab.dep_tree import extract_sub_tree, validate_dependencies, AnalysedDependent
from fab.mo import add_mo_commented_file_deps
from fab.parse import AnalysedFile, EmptySourceFile
from fab.parse.c import AnalysedC, CAnalyser
from fab.parse.fortran import AnalysedFortran, FortranParserWorkaround, FortranAnalyser
from fab.steps import run_mp, step
from fab.util import TimerLogger, by_type

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_GETTER = CollectionConcat([
    ArtefactStore.FORTRAN_BUILD_FILES,
    ArtefactStore.C_BUILD_FILES,
    # todo: this is lfric stuff so might be better placed elsewhere
    SuffixFilter('psyclone_output', '.f90'),
    'preprocessed_psyclone',  # todo: this is no longer a collection, remove
    'configurator_output',
])


# todo: split out c and fortran? this class is still a bit big
# This has all been done as a single step, for now, because we don't have a simple mp pattern
# (i.e we don't have a list of artefacts and a function to feed them through).
@step
def analyse(
        config,
        source: Optional[ArtefactsGetter] = None,
        root_symbol: Optional[Union[str, List[str]]] = None,
        find_programs: bool = False,
        std: str = "f2008",
        special_measure_analysis_results: Optional[Iterable[FortranParserWorkaround]] = None,
        unreferenced_deps: Optional[Iterable[str]] = None,
        ignore_mod_deps: Optional[Iterable[str]] = None,
        name='analyser'):
    """
    Produce one or more build trees by analysing source code dependencies.

    The resulting artefact collection is a mapping from root symbol to build tree.
    The name of this artefact collection is taken from :py:const:`fab.constants.BUILD_TREES`.

    If no artefact getter is specified in *source*, a default is used which provides input files
    from multiple artefact collections, including the default C and Fortran preprocessor outputs
    and any source files with a 'little' *.f90* extension.

    A build tree is produced for every root symbol specified in *root_symbol*, which can be a string or list of.
    This is how we create executable files. If no root symbol is specified, a single tree of the entire source
    is produced (with a root symbol of `None`). This is how we create shared and static libraries.

    :param config:
        The :class:`fab.build_config.BuildConfig` object where we can read settings
        such as the project workspace folder or the multiprocessing flag.
    :param source:
        An :class:`~fab.util.ArtefactsGetter` to get the source files.
    :param find_programs:
        Instructs the analyser to automatically identify program definitions in the source.
        Alternatively, the required programs can be specified with the root_symbol argument.
    :param root_symbol:
        When building an executable, provide the Fortran Program name(s), or 'main' for C.
        If None, build tree extraction will not be performed and the entire source will be used
        as the build tree - for building a shared or static library.
    :param std:
        The fortran standard, passed through to fparser2. Defaults to 'f2008'.
    :param special_measure_analysis_results:
        When a language parser cannot parse a valid source file, we can manually provide the expected analysis
        results with this argument.
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

    if find_programs and root_symbol:
        raise ValueError("find_programs and root_symbol can't be used together")

    source_getter = source or DEFAULT_SOURCE_GETTER
    root_symbols: Optional[List[str]] = [root_symbol] if isinstance(root_symbol, str) else root_symbol
    special_measure_analysis_results = list(special_measure_analysis_results or [])
    unreferenced_deps = list(unreferenced_deps or [])

    # todo: these seem more like functions
    fortran_analyser = FortranAnalyser(std=std, ignore_mod_deps=ignore_mod_deps)
    c_analyser = CAnalyser()

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

    # todo: code smell - refactor (in another PR to keep things small)
    fortran_analyser._config = config
    c_analyser._config = config

    # parse
    files: List[Path] = source_getter(config.artefact_store)
    analysed_files = _parse_files(config, files=files, fortran_analyser=fortran_analyser, c_analyser=c_analyser)
    _add_manual_results(special_measure_analysis_results, analysed_files)

    # shall we search the results for fortran programs and a c function called main?
    if find_programs:
        # find fortran programs
        sets_of_programs = [af.program_defs for af in by_type(analysed_files, AnalysedFortran)]
        root_symbols = list(chain(*sets_of_programs))

        # find c main()
        c_with_main = list(filter(lambda c: 'main' in c.symbol_defs, by_type(analysed_files, AnalysedC)))
        if c_with_main:
            root_symbols.append('main')
            if len(c_with_main) > 1:
                raise FabException("multiple c main() functions found")

        logger.info(f'automatically found the following programs to build: {", ".join(root_symbols)}')

    # analyse
    project_source_tree, symbol_table = _analyse_dependencies(analysed_files)

    # add the file dependencies for MO FCM's "DEPENDS ON:" commented file deps (being removed soon)
    with TimerLogger("adding MO FCM 'DEPENDS ON:' file dependency comments"):
        add_mo_commented_file_deps(project_source_tree)

    logger.info(f"source tree size {len(project_source_tree)}")

    # extract "build trees" for executables.
    if root_symbols:
        build_trees = _extract_build_trees(root_symbols, project_source_tree, symbol_table)
    else:
        build_trees = {None: project_source_tree}

    # throw in any extra source we need, which Fab can't automatically detect
    for build_tree in build_trees.values():
        _add_unreferenced_deps(unreferenced_deps, symbol_table, project_source_tree, build_tree)
        validate_dependencies(build_tree)

    config.artefact_store[BUILD_TREES] = build_trees


def _analyse_dependencies(analysed_files: Iterable[AnalysedDependent]):
    """
    Build a source dependency tree for the entire source.

    """
    with TimerLogger("converting symbol dependencies to file dependencies"):
        # map symbols to the files they're in
        symbol_table: Dict[str, Path] = _gen_symbol_table(analysed_files)

        # fill in the file deps attribute in the analysed file objects
        _gen_file_deps(analysed_files, symbol_table)

    # build the tree
    # the nodes refer to other nodes via the file dependencies we just made, which are keys into this dict
    source_tree: Dict[Path, AnalysedDependent] = {a.fpath: a for a in analysed_files}

    return source_tree, symbol_table


def _extract_build_trees(root_symbols, project_source_tree, symbol_table):
    """
    Find the subset of files needed to build each root symbol (executable).

    Assumes we have been given a root symbol(s) or we wouldn't have been called.
    Returns a build tree for every root symbol.

    """
    build_trees = {}
    assert root_symbols is not None
    for root in root_symbols:
        with TimerLogger(f"extracting build tree for root '{root}'"):
            build_tree = extract_sub_tree(project_source_tree, symbol_table[root], verbose=False)

        logger.info(f"target source tree size {len(build_tree)} (target '{symbol_table[root]}')")
        build_trees[root] = build_tree

    return build_trees


def _parse_files(config, files: List[Path], fortran_analyser, c_analyser) -> Set[AnalysedDependent]:
    """
    Determine the symbols which are defined in, and used by, each file.

    Returns the analysed_fortran and analysed_c as lists of :class:`~fab.dep_tree.AnalysedDependent`
    with no file dependencies, to be filled in later.

    """
    # fortran
    fortran_files = set(filter(lambda f: f.suffix == '.f90', files))
    with TimerLogger(f"analysing {len(fortran_files)} preprocessed fortran files"):
        fortran_results = run_mp(config, items=fortran_files, func=fortran_analyser.run)
    fortran_analyses, fortran_artefacts = zip(*fortran_results) if fortran_results else (tuple(), tuple())

    # warn about naughty fortran usage
    if fortran_analyser.depends_on_comment_found:
        warnings.warn("deprecated 'DEPENDS ON:' comment found in fortran code")

    # c
    c_files = set(filter(lambda f: f.suffix == '.c', files))
    with TimerLogger(f"analysing {len(c_files)} preprocessed c files"):
        # The C analyser hangs with multiprocessing in Python 3.7!
        # Override the multiprocessing flag.
        no_multiprocessing = False
        if sys.version.startswith('3.7'):
            warnings.warn('Python 3.7 detected. Disabling multiprocessing for C analysis.')
            no_multiprocessing = True
        c_results = run_mp(config, items=c_files, func=c_analyser.run, no_multiprocessing=no_multiprocessing)
    c_analyses, c_artefacts = zip(*c_results) if c_results else (tuple(), tuple())

    # Check for parse errors but don't fail. The failed files might not be required.
    analyses = fortran_analyses + c_analyses
    exceptions = list(by_type(analyses, Exception))
    if exceptions:
        err_str = '\n\n'.join(map(str, exceptions))
        print(f"\nThere were {len(exceptions)} analysis errors:\n\n{err_str}\n\n", file=sys.stderr)

    # record the artefacts as being current
    artefacts = by_type(fortran_artefacts + c_artefacts, Path)
    config.add_current_prebuilds(artefacts)

    # ignore empty files
    analysed_files = by_type(analyses, AnalysedFile)
    non_empty = {af for af in analysed_files if not isinstance(af, EmptySourceFile)}
    return non_empty


def _add_manual_results(special_measure_analysis_results, analysed_files: Set[AnalysedDependent]):
    # add manual analysis results for files which could not be parsed
    if special_measure_analysis_results:
        warnings.warn("SPECIAL MEASURE: injecting user-defined analysis results")
        already_present = {af.fpath for af in analysed_files}

        for r in special_measure_analysis_results:
            if r.fpath in already_present:
                # Note: This exception stops the user from being able to override results for files
                # which don't *crash* the parser. We don't have a use case to do this, but it's worth noting.
                # If we want to allow this we can raise a warning instead of an exception.
                raise ValueError(f'Unnecessary ParserWorkaround for {r.fpath}')
            analysed_files.add(r.as_analysed_fortran())

        logger.info(f'added {len(special_measure_analysis_results)} manual analysis results')


def _gen_symbol_table(analysed_files: Iterable[AnalysedDependent]) -> Dict[str, Path]:
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


def _gen_file_deps(analysed_files: Iterable[AnalysedDependent], symbols: Dict[str, Path]):
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


def _add_unreferenced_deps(unreferenced_deps, symbol_table: Dict[str, Path],
                           all_analysed_files: Dict[Path, AnalysedDependent],
                           build_tree: Dict[Path, AnalysedDependent]):
    """
    Add files to the build tree.

    This is used for building Fortran code which Fab doesn't know is a dependency.

    """
    if not unreferenced_deps:
        return
    logger.info(f"Adding {len(unreferenced_deps or [])} unreferenced dependencies")

    for symbol_dep in unreferenced_deps:

        # what file is the symbol in?
        analysed_fpath = symbol_table.get(symbol_dep)
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

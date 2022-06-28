##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
C and Fortran analysis, creating build trees.

"""

import csv
import logging
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Set, Optional, Union

from fab.constants import BUILD_TREES
from fab.dep_tree import AnalysedFile, add_mo_commented_file_deps, extract_sub_tree, EmptySourceFile, \
    validate_dependencies
from fab.steps import Step
from fab.tasks.c import CAnalyser
from fab.tasks.fortran import FortranAnalyser
from fab.util import HashedFile, do_checksum, log_or_dot_finish, TimerLogger
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
                 source: ArtefactsGetter = None,
                 root_symbol: Optional[Union[str, List[str]]] = None,  # todo: iterable is more correct
                 std="f2008",
                 special_measure_analysis_results=None,
                 unreferenced_deps=None,
                 ignore_mod_deps=None,
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
            A list of symbols which are needed for the build, but which cannot be automatically
            determined. For example, functions that are called without a module use statement. Assuming the files
            containing these symbols are present and will be analysed, those files and all their dependencies
            will be added to the build tree(s).
        :param ignore_mod_deps:
            Third party Fortran module names to be ignored.
        :param name:
            Defaults to 'analyser'

        """
        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.root_symbols: Optional[List[str]] = [root_symbol] if isinstance(root_symbol, str) else root_symbol
        self.special_measure_analysis_results: List[AnalysedFile] = special_measure_analysis_results or []
        self.unreferenced_deps: List[str] = unreferenced_deps or []

        # todo: these seem more like functions
        self.fortran_analyser = FortranAnalyser(std=std, ignore_mod_deps=ignore_mod_deps)
        self.c_analyser = CAnalyser()

    def run(self, artefact_store, config):
        """
        Creates the *build_trees* artefact from the files in `self.source_getter`.

        Steps, in order:
            - Create a hash of every source file. Used to check if it's already been analysed.
            - Parse the C and Fortran files to find external symbol definitions and dependencies in each file.
                - Analysis results are stored in a csv as-we-go, so analysis can be resumed if interrupted.
            - Create a 'symbol table' recording which file each symbol is in.
            - Work out the file dependencies from the symbol dependencies.
                - At this point we have a source tree for the entire source.
            - (Optionally) Extract a sub tree for every root symbol, if provided. For building executables.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefact_store, config)

        analysed_files = self._analyse_source_code(artefact_store)

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

        # throw in any extra source we need, which Fab can't automatically detect (i.e. not using use statements)
        for build_tree in build_trees.values():
            self._add_unreferenced_deps(symbols, project_source_tree, build_tree)
            validate_dependencies(build_tree)

        artefact_store[BUILD_TREES] = build_trees

    def _analyse_source_code(self, artefact_store) -> Set[AnalysedFile]:
        """
        Find the symbol defs and deps in each file.

        This is slow so we record our progress as we go.

        """
        # get a list of all the files we want to analyse
        files: List[Path] = self.source_getter(artefact_store)

        # take hashes of all the files we want to analyse
        with TimerLogger(f"generating {len(files)} file hashes"):
            file_hashes = self._get_file_checksums(files)

        with TimerLogger("loading previous analysis results"):
            prev_results = self._load_analysis_results(latest_file_hashes=file_hashes)
            changed, unchanged = self._what_needs_reanalysing(prev_results=prev_results, latest_file_hashes=file_hashes)

        with TimerLogger("analysing files"):
            with self._new_analysis_file(unchanged) as csv_writer:
                freshly_analysed_fortran, freshly_analysed_c = self._parse_files(changed, csv_writer)

        return unchanged | freshly_analysed_fortran | freshly_analysed_c

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

    def _parse_files(self, to_analyse: Iterable[HashedFile], analysis_dict_writer: csv.DictWriter) -> \
            Tuple[Set[AnalysedFile], Set[AnalysedFile]]:
        """
        Determine the symbols which are defined in, and used by, each file.

        Returns the analysed_fortran and analysed_c as lists of :class:`~fab.dep_tree.AnalysedFile`
        with no file dependencies, to be filled in later.

        """
        # fortran
        fortran_files = set(filter(lambda f: f.fpath.suffix == '.f90', to_analyse))
        with TimerLogger(f"analysing {len(fortran_files)} preprocessed fortran files"):
            analysed_fortran, fortran_exceptions = self._analyse_file_type(
                fpaths=fortran_files, analyser=self.fortran_analyser.run, dict_writer=analysis_dict_writer)

        # c
        c_files = set(filter(lambda f: f.fpath.suffix == '.c', to_analyse))
        with TimerLogger(f"analysing {len(c_files)} preprocessed c files"):
            analysed_c, c_exceptions = self._analyse_file_type(
                fpaths=c_files, analyser=self.c_analyser.run, dict_writer=analysis_dict_writer)

        # errors?
        all_exceptions = fortran_exceptions | c_exceptions
        if all_exceptions:
            logger.error(f"{len(all_exceptions)} analysis errors")
            errs_str = "\n\n".join(map(str, all_exceptions))
            logger.debug(f"\nSummary of analysis errors:\n{errs_str}")

        # warn about naughty fortran usage?
        if self.fortran_analyser.depends_on_comment_found:
            warnings.warn("not recommended 'DEPENDS ON:' comment found in fortran code")

        return analysed_fortran, analysed_c

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
                    if not file_dep:
                        deps_not_found.add(symbol_dep)
                        logger.debug(f"not found {symbol_dep} for {analysed_file.fpath}")
                        continue
                    analysed_file.file_deps.add(file_dep)
        if deps_not_found:
            logger.info(f"{len(deps_not_found)} deps not found")

    def _get_file_checksums(self, fpaths: Iterable[Path]) -> Dict[Path, int]:
        mp_results = self.run_mp(items=fpaths, func=do_checksum)
        latest_file_hashes: Dict[Path, int] = {fh.fpath: fh.file_hash for fh in mp_results}
        return latest_file_hashes

    def _load_analysis_results(self, latest_file_hashes: Dict[Path, int]) -> Dict[Path, AnalysedFile]:
        """
        The analysis file includes the hash of each file when we last analysed it.
        We discard previous results from files which are no longer present.

        """
        prev_results: Dict[Path, AnalysedFile] = dict()
        try:
            with open(self._config.project_workspace / "__analysis.csv", "rt") as csv_file:
                dict_reader = csv.DictReader(csv_file)
                for row in dict_reader:
                    analysed_file = AnalysedFile.from_dict(row)

                    # file no longer there?
                    if analysed_file.fpath not in latest_file_hashes:
                        logger.info(f"file no longer present: {analysed_file.fpath}")
                        continue

                    # ok, we have previously analysed this file
                    prev_results[analysed_file.fpath] = analysed_file

            logger.info(f"loaded {len(prev_results)} previous analysis results")
        except FileNotFoundError:
            logger.info("no previous analysis results")
            pass

        return prev_results

    def _what_needs_reanalysing(self, prev_results: Dict[Path, AnalysedFile], latest_file_hashes: Dict[Path, int]) -> \
            Tuple[Set[HashedFile], Set[AnalysedFile]]:
        """
        Determine which files have changed since they were last analysed.

        Returns, in a tuple:
             - The changed files as a set of HashedFile
             - The unchanged files as a set of AnalysedFile

        """
        # work out what needs to be reanalysed
        changed: Set[HashedFile] = set()
        unchanged: Set[AnalysedFile] = set()
        for latest_fpath, latest_hash in latest_file_hashes.items():
            # what happened last time we analysed this file?
            prev_pu = prev_results.get(latest_fpath)
            if (not prev_pu) or prev_pu.file_hash != latest_hash:
                changed.add(HashedFile(latest_fpath, latest_hash))
            else:
                unchanged.add(prev_pu)

        logger.info(f"{len(unchanged)} files already analysed, {len(changed)} to analyse")

        return changed, unchanged

    # todo: it might be better to create an analysis file per source file.
    @contextmanager
    def _new_analysis_file(self, unchanged: Iterable[AnalysedFile]):
        """
        Create the analysis file from scratch, containing any content from its previous version which is still valid.

        The returned context is a csv.DictWriter.
        """
        with TimerLogger("starting analysis progress file"):
            analysis_progress_file = open(self._config.project_workspace / "__analysis.csv", "wt")
            analysis_dict_writer = csv.DictWriter(analysis_progress_file, fieldnames=AnalysedFile.field_names())
            analysis_dict_writer.writeheader()

            # re-write the progress so far
            unchanged_rows = (pu.as_dict() for pu in unchanged)
            analysis_dict_writer.writerows(unchanged_rows)
            analysis_progress_file.flush()

        yield analysis_dict_writer

        analysis_progress_file.close()

    def _analyse_file_type(self, fpaths: Iterable[HashedFile], analyser,
                           dict_writer: csv.DictWriter) -> Tuple[Set[AnalysedFile], Set[Exception]]:
        """
        Pass the files to the analyser and check the results for errors and empty files.

        Returns a list of :class:`~fab.dep_tree.AnalysedFile` and a list of exceptions.

        """
        new_program_units: Set[AnalysedFile] = set()
        exceptions = set()

        def result_handler(analysis_results):
            for af in analysis_results:
                # todo: use by_type()? we'd have to make sure it can't ever change to stop us saving on-the-fly
                if isinstance(af, EmptySourceFile):
                    continue
                elif isinstance(af, Exception):
                    logger.error(f"\n{af}")
                    exceptions.add(af)
                elif isinstance(af, AnalysedFile):
                    new_program_units.add(af)
                    dict_writer.writerow(af.as_dict())
                else:
                    raise RuntimeError(f"Unexpected analysis result type: {af}")
            log_or_dot_finish(logger)

        # we use imap here so we can save the analysis progress as we go
        self.run_mp_imap(items=fpaths, func=analyser, result_handler=result_handler)

        return new_program_units, exceptions

    def _add_unreferenced_deps(self, symbols: Dict[str, Path],
                               all_analysed_files: Dict[Path, AnalysedFile], build_tree: Dict[Path, AnalysedFile]):
        """
        Add files to the build tree.

        This is used for building Fortran code which does not use modules to declare dependencies.
        In this case, Fab cannot determine those dependencies and the user is required to list them.

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
            sub_tree = extract_sub_tree(src_tree=all_analysed_files, key=analysed_fpath)
            build_tree.update(sub_tree)

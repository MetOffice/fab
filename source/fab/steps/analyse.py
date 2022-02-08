"""
C and Fortran analysis, creating a build tree.

"""

import csv
import logging
import warnings
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Set

from fab.dep_tree import AnalysedFile, add_mo_commented_file_deps, extract_sub_tree, EmptySourceFile, \
    validate_build_tree

from fab.steps import Step
from fab.tasks.c import CAnalyser
from fab.tasks.fortran import FortranAnalyser
from fab.util import time_logger, HashedFile, do_checksum, log_or_dot_finish, Artefacts, SourceGetter

logger = logging.getLogger('fab')


DEFAULT_SOURCE_GETTER = Artefacts(['preprocessed_c', 'preprocessed_fortran'])


# todo: split out c and fortran?
# This has all been done as a single step (for now) because we don't have a simple list of artefacts and
# a function to process them one at a time.
class Analyse(Step):

    # todo: this docstring is not appearing in sphinx renders
    def __init__(self,
                 root_symbol, source: SourceGetter=None, std="f2008",
                 special_measure_analysis_results=None, unreferenced_deps=None, name='analyser'):
        """

        Args:
            - source: A :class:`~fab.util.SourceGetter`.
            - root_symbol: When building an executable, provide the Fortran Program name, or 'main' for C.
                If None, target tree extraction will not be performed and the whole codebase will be returned
                in the build tree, as when building a compiled object archive.
            - std: The fortran standard, passed through to fparser2. Defaults to 'f2008'.
            - special_measure_analysis_results: When fparser2 cannot parse a "valid" Fortran file,
                we can manually provide the expected analysis results with this argument.
                Only the symbol definitions and dependencies need be provided.
            - unreferenced_deps: A list of symbols which are needed for the build, but which cannot be automatically
                determined. For example, functions that are called without a module use statement. Assuming the files
                containing these symbols will been analysed, those files and all their dependencies
                will be added to the build tree.
            - name: Defaults to 'analyser'

        """
        super().__init__(name)
        self.source_getter = source or DEFAULT_SOURCE_GETTER
        self.root_symbol: str = root_symbol
        self.special_measure_analysis_results: List[AnalysedFile] = special_measure_analysis_results or []
        self.unreferenced_deps: List[str] = unreferenced_deps or []

        # todo: these seem more like functions
        self.fortran_analyser = FortranAnalyser(std=std)
        self.c_analyser = CAnalyser()

    def run(self, artefacts, config):
        """
        Creates the *build_tree* artefact: Dict[Path, AnalysedFile] from the files in `self.source_getter`.

        Steps, in order:
            - Creates a hash of every artefact, used to check if it's already been analysed.
            - Parse the C and Fortran files to find the symbol definitions and depndencies in each file.
                - Analysis results are stored in a csv as-we-go, so analysis can be resumed if interrupted.
            - Creates a symbol table for external symbols: Dict[symbol, Path]
            - Work out the file dependencies from the symbol dependencies.
            - (Optionally) Prune the file dependency tree for the root symbol, if given.

        This step uses multiprocessing, unless disabled in the :class:`~fab.steps.Step` class.

        """
        super().run(artefacts, config)

        files = self.source_getter(artefacts)

        # take hashes of all the files we preprocessed
        with time_logger(f"getting {len(files)} hashes"):
            preprocessed_hashes = self._get_latest_checksums(files)

        with time_logger("loading previous analysis results"):
            changed, unchanged = self._load_analysis_results(preprocessed_hashes)

        with time_logger("analysing files"):
            with self._new_analysis_file(unchanged) as csv_writer:
                analysed_fortran, analysed_c = self._parse_files(changed, csv_writer)
        all_analysed_files: Dict[Path, AnalysedFile] = {a.fpath: a for a in unchanged + analysed_fortran + analysed_c}

        # Make "external" symbol table
        with time_logger("creating symbol lookup"):
            symbols: Dict[str, Path] = self._gen_symbol_table(all_analysed_files)

        # turn symbol deps into file deps
        self._gen_file_deps(all_analysed_files, symbols)

        #  find the file dependencies for UM "DEPENDS ON:" commented file deps
        with time_logger("adding MO 'DEPENDS ON:' file dependency comments"):
            add_mo_commented_file_deps(analysed_fortran, analysed_c)

        logger.info(f"source tree size {len(all_analysed_files)}")

        # Target tree extraction - for building executables.
        if self.root_symbol:
            with time_logger("extracting target tree"):
                build_tree = extract_sub_tree(all_analysed_files, symbols[self.root_symbol], verbose=False)
            logger.info(f"build tree size {len(build_tree)} (target '{symbols[self.root_symbol]}')")
        # When building library ".so" files, no target is needed.
        else:
            logger.info("no target specified, building everything")
            build_tree = all_analysed_files

        # Recursively add any unreferenced dependencies
        # (a fortran routine called without a use statement).
        self._add_unreferenced_deps(symbols, all_analysed_files, build_tree)

        validate_build_tree(build_tree)

        artefacts['build_tree'] = build_tree

        # if self.dump_source_tree:
        #     with open(datetime.now().strftime(f"tmp/af2_{runtime_str}.txt"), "wt") as outfile:
        #         sorted_files = sorted(all_analysed_files.values(), key=lambda af: af.fpath)
        #         for af in sorted_files:
        #             af.dump(outfile)

    def _parse_files(self,
                    to_analyse_by_type: Dict[str, List[HashedFile]],
                    analysis_dict_writer: csv.DictWriter):
        """
        Determine the symbols which are defined in, and used by, each file.

        Returns the analysed_fortran and analysed_c as lists of :class:`~fab.dep_tree.AnalysedFile`
        with no file dependencies, to be filled in later.

        """
        # fortran
        fortran_files = to_analyse_by_type[".f90"]
        with time_logger(f"analysing {len(fortran_files)} preprocessed fortran files"):
            analysed_fortran, fortran_exceptions = self._analyse_file_type(
                fpaths=fortran_files, analyser=self.fortran_analyser.run, dict_writer=analysis_dict_writer)

        # c
        c_files = to_analyse_by_type[".c"]
        with time_logger(f"analysing {len(c_files)} preprocessed c files"):
            analysed_c, c_exceptions = self._analyse_file_type(
                fpaths=c_files, analyser=self.c_analyser.run, dict_writer=analysis_dict_writer)

        # errors?
        all_exceptions = fortran_exceptions | c_exceptions
        if all_exceptions:
            logger.error(f"{len(all_exceptions)} analysis errors")
            errs_str = "\n\n".join(map(str, all_exceptions))
            logger.debug(f"\nSummary of analysis errors:\n{errs_str}")
            # exit(1)

        # warn about naughty fortran usage?
        if self.fortran_analyser.depends_on_comment_found:
            warnings.warn("deprecated 'DEPENDS ON:' comment found in fortran code")

        return analysed_fortran, analysed_c

    def _gen_symbol_table(self, all_analysed_files: Dict[Path, AnalysedFile]):
        """
        Create a dictionary mapping symbol names to the files in which they appear.

        """
        # add special measure symbols for files which could not be parsed
        if self.special_measure_analysis_results:
            for analysed_file in self.special_measure_analysis_results:
                warnings.warn(f"SPECIAL MEASURE for {analysed_file.fpath}: injecting user-defined analysis results")
                all_analysed_files[analysed_file.fpath] = analysed_file

        # map symbols to the files in which they're defined
        symbols = dict()
        duplicates = []
        for analysed_file in all_analysed_files.values():
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

    def _gen_file_deps(self, all_analysed_files, symbols):
        """
        Use the symbol table to convert symbol dependencies into file dependencies.

        """
        deps_not_found = set()
        with time_logger("converting symbol to file deps"):
            for analysed_file in all_analysed_files.values():
                for symbol_dep in analysed_file.symbol_deps:
                    file_dep = symbols.get(symbol_dep)
                    if not file_dep:
                        deps_not_found.add(symbol_dep)
                        logger.debug(f"(might not matter) not found {symbol_dep} for {analysed_file.fpath}")
                        continue
                    analysed_file.file_deps.add(file_dep)
        if deps_not_found:
            logger.info(f"{len(deps_not_found)} deps not found")

    def _get_latest_checksums(self, fpaths: Iterable[Path]) -> Dict[Path, int]:
        mp_results = self.run_mp(items=fpaths, func=do_checksum)
        latest_file_hashes: Dict[Path, int] = {fh.fpath: fh.file_hash for fh in mp_results}
        return latest_file_hashes

    def _load_analysis_results(self, latest_file_hashes) -> Tuple[Dict[str, List[HashedFile]], List[AnalysedFile]]:
        # This function tells us which files have changed since they were last analysed.
        # The analysis file includes the hash of the file when we last analysed it.
        # We discard previous results from files which are no longer present.
        prev_results: Dict[Path, AnalysedFile] = dict()
        try:
            with open(self._config.workspace / "__analysis.csv", "rt") as csv_file:
                dict_reader = csv.DictReader(csv_file)
                for row in dict_reader:
                    analysed_file = AnalysedFile.from_dict(row)

                    # file no longer there?
                    if analysed_file.fpath not in latest_file_hashes:
                        logger.info(f"a file has gone: {analysed_file.fpath}")
                        continue

                    # ok, we have previously analysed this file
                    prev_results[analysed_file.fpath] = analysed_file

            logger.info(f"loaded {len(prev_results)} previous analysis results")
        except FileNotFoundError:
            logger.info("no previous analysis results")
            pass

        # work out what needs to be reanalysed
        unchanged: List[AnalysedFile] = []  # todo: use a set?
        changed: Dict[str, List[HashedFile]] = defaultdict(list)  # suffix -> files
        for latest_fpath, latest_hash in latest_file_hashes.items():
            # what happened last time we analysed this file?
            prev_pu = prev_results.get(latest_fpath)
            if (not prev_pu) or prev_pu.file_hash != latest_hash:
                changed[latest_fpath.suffix].append(HashedFile(latest_fpath, latest_hash))
            else:
                unchanged.append(prev_pu)

        for suffix, to_analyse in changed.items():
            logger.info(f"{len(unchanged)} {suffix} files already analysed, {len(to_analyse)} to analyse")

        return changed, unchanged

    @contextmanager
    def _new_analysis_file(self, unchanged: List[AnalysedFile]) -> csv.DictWriter:
        # Open a new analysis file, populated with work already done in previous runs.
        # We re-write the successfully read contents of the analysis file each time,
        # for robustness against data corruption (otherwise we could just open with "wt+").
        with time_logger("starting analysis progress file"):
            analysis_progress_file = open(self._config.workspace / "__analysis.csv", "wt")
            analysis_dict_writer = csv.DictWriter(analysis_progress_file, fieldnames=AnalysedFile.field_names())
            analysis_dict_writer.writeheader()

            # re-write the progress so far
            unchanged_rows = (pu.as_dict() for pu in unchanged)
            analysis_dict_writer.writerows(unchanged_rows)
            analysis_progress_file.flush()

        yield analysis_dict_writer

        analysis_progress_file.close()

    def _analyse_file_type(self,
                          fpaths: List[HashedFile],
                          analyser,
                          dict_writer: csv.DictWriter) -> Tuple[List[AnalysedFile], Set[Exception]]:
        """
        Pass the files to the analyser and check the results for errors and empty files.

        Returns a list of :class:`~fab.dep_tree.AnalysedFile` and a list of exceptions.

        """
        # todo: return a set?
        new_program_units: List[AnalysedFile] = []
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
                    new_program_units.append(af)
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
        Add files to the target tree.

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

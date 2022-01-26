import csv
import logging
import multiprocessing
import warnings
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Set

from fab.builder import logger
from fab.dep_tree import AnalysedFile, add_mo_commented_file_deps, extract_sub_tree, EmptySourceFile, \
    validate_build_tree

from fab.steps import Step
from fab.tasks.c import CAnalyser
from fab.tasks.fortran import FortranAnalyser
from fab.util import time_logger, HashedFile, do_checksum, log_or_dot_finish

logger = logging.getLogger('fab')


class Analyse(Step):
    """
    This has been done as a single step because the use of mp does not fit the (current) MPStep class
    because we don't have a simple list of artefacts with a function to process one at a time.

    """
    def __init__(self, workspace, name='analyser', root_symbol=None,
                 special_measure_analysis_results=None, unreferenced_deps=None):
        super().__init__(name)
        self.workspace = workspace
        self.root_symbol = root_symbol
        self.special_measure_analysis_results = special_measure_analysis_results or []
        self.unreferenced_deps = unreferenced_deps or []

        # todo: these seem more like functions
        self.fortran_analyser = FortranAnalyser()
        self.c_analyser = CAnalyser()

    def run(self, artefacts):
        # take hashes of all the files we preprocessed
        with time_logger(f"getting {len(artefacts['preprocessed_fortran']) + len(artefacts['preprocessed_c'])} file hashes"):
            preprocessed_hashes = self.get_latest_checksums(artefacts['preprocessed_fortran'] | artefacts['preprocessed_c'])

        # analyse c and fortran
        with self.analysis_progress(preprocessed_hashes) as (unchanged, to_analyse, analysis_dict_writer):
            analysed_c, analysed_fortran = self.analyse(to_analyse, analysis_dict_writer)
        all_analysed_files: Dict[Path, AnalysedFile] = {a.fpath: a for a in unchanged + analysed_fortran + analysed_c}

        # add special measure analysis results
        if self.special_measure_analysis_results:
            for analysed_file in self.special_measure_analysis_results:
                # todo: create a special measures notification function? with a loud summary at the end of the build?
                warnings.warn(f"SPECIAL MEASURE for {analysed_file.fpath}: injecting user-defined analysis results")
                all_analysed_files[analysed_file.fpath] = analysed_file

        # Make "external" symbol table
        with time_logger("creating symbol lookup"):
            symbols: Dict[str, Path] = gen_symbol_table(all_analysed_files)

        # turn symbol deps into file deps
        deps_not_found = set()
        with time_logger("converting symbol to file deps"):
            for analysed_file in all_analysed_files.values():
                for symbol_dep in analysed_file.symbol_deps:
                    # todo: does file_deps belong in there?
                    file_dep = symbols.get(symbol_dep)
                    if not file_dep:
                        deps_not_found.add(symbol_dep)
                        logger.debug(f"(might not matter) not found {symbol_dep} for {analysed_file.fpath}")
                        continue
                    analysed_file.file_deps.add(file_dep)
        if deps_not_found:
            logger.info(f"{len(deps_not_found)} deps not found")

        #  find the files for UM "DEPENDS ON:" commented file deps
        with time_logger("adding MO 'DEPENDS ON:' file dependency comments"):
            add_mo_commented_file_deps(analysed_fortran, analysed_c)

        # TODO: document this: when there's duplicate symbols, the size of the (possibly wrong) build tree can vary...
        # Target tree extraction - for building executables.
        # When building library ".so" files, no target is needed.
        logger.info(f"source tree size {len(all_analysed_files)}")
        if self.root_symbol:
            with time_logger("extracting target tree"):
                build_tree = extract_sub_tree(all_analysed_files, symbols[self.root_symbol], verbose=False)
            logger.info(f"build tree size {len(build_tree)} (target '{symbols[self.root_symbol]}')")
        else:
            logger.info("no target specified, building everything")
            build_tree = all_analysed_files

        # Recursively add any unreferenced dependencies
        # (a fortran routine called without a use statement).
        # This is driven by the config list "unreferenced-dependencies"
        self.add_unreferenced_deps(symbols, all_analysed_files, build_tree)

        validate_build_tree(build_tree)

        artefacts['build_tree'] = build_tree

        # if self.dump_source_tree:
        #     with open(datetime.now().strftime(f"tmp/af2_{runtime_str}.txt"), "wt") as outfile:
        #         sorted_files = sorted(all_analysed_files.values(), key=lambda af: af.fpath)
        #         for af in sorted_files:
        #             af.dump(outfile)

    def analyse(self, to_analyse_by_type: Dict[str, List[HashedFile]], analysis_dict_writer: csv.DictWriter) \
            -> Tuple[List[AnalysedFile], List[AnalysedFile]]:

        fortran_files = to_analyse_by_type[".f90"]
        with time_logger(f"analysing {len(fortran_files)} preprocessed fortran files"):
            analysed_fortran, fortran_exceptions = self.analyse_file_type(
                fpaths=fortran_files, analyser=self.fortran_analyser.run, dict_writer=analysis_dict_writer)
        # did we find naughty fortran code?
        if self.fortran_analyser.depends_on_comment_found:
            warnings.warn("deprecated 'DEPENDS ON:' comment found in fortran code")

        c_files = to_analyse_by_type[".c"]
        with time_logger(f"analysing {len(c_files)} preprocessed c files"):
            analysed_c, c_exceptions = self.analyse_file_type(
                fpaths=c_files, analyser=self.c_analyser.run, dict_writer=analysis_dict_writer)

        # analysis errors?
        all_exceptions = fortran_exceptions | c_exceptions
        if all_exceptions:
            logger.error(f"{len(all_exceptions)} analysis errors")
            errs_str = "\n\n".join(map(str, all_exceptions))
            logger.debug(f"\nSummary of analysis errors:\n{errs_str}")
            # exit(1)

        return analysed_c, analysed_fortran

    def get_latest_checksums(self, fpaths: Iterable[Path]) -> Dict[Path, int]:
        mp_results = self.run_mp(items=fpaths, func=do_checksum)
        latest_file_hashes: Dict[Path, int] = {fh.fpath: fh.file_hash for fh in mp_results}
        return latest_file_hashes

    @contextmanager
    def analysis_progress(self, preprocessed_hashes) -> Tuple[List[AnalysedFile],
                                                              Dict[str, List[HashedFile]], csv.DictWriter]:
        """Open a new analysis progress file, populated with work already done in previous runs."""

        with time_logger("loading analysis results"):
            to_analyse, unchanged = self.load_analysis_results(preprocessed_hashes)

        with time_logger("starting analysis progress file"):
            unchanged_rows = (pu.as_dict() for pu in unchanged)
            analysis_progress_file = open(self.workspace / "__analysis.csv", "wt")
            analysis_dict_writer = csv.DictWriter(analysis_progress_file, fieldnames=AnalysedFile.field_names())
            analysis_dict_writer.writeheader()
            analysis_dict_writer.writerows(unchanged_rows)
            analysis_progress_file.flush()

        to_analyse_by_type: Dict[List[HashedFile]] = defaultdict(list)
        for hashed_file in to_analyse:
            to_analyse_by_type[hashed_file.fpath.suffix].append(hashed_file)

        yield unchanged, to_analyse_by_type, analysis_dict_writer

        analysis_progress_file.close()

    def load_analysis_results(self, latest_file_hashes) -> Tuple[List[HashedFile], List[AnalysedFile]]:
        # Load analysis results from previous run.
        # Includes the hash of the file when we last analysed it.
        # Note: it would be easy to switch to a database instead of a csv file
        prev_results: Dict[Path, AnalysedFile] = dict()
        try:
            with open(self.workspace / "__analysis.csv", "rt") as csv_file:
                dict_reader = csv.DictReader(csv_file)
                for row in dict_reader:
                    current_file = AnalysedFile.from_dict(row)

                    # file no longer there?
                    if current_file.fpath not in latest_file_hashes:
                        logger.info(f"a file has gone: {current_file.fpath}")
                        continue

                    # ok, we have previously analysed this file
                    prev_results[current_file.fpath] = current_file

            logger.info(f"loaded {len(prev_results)} previous analysis results")
        except FileNotFoundError:
            logger.info("no previous analysis results")
            pass

        # work out what needs to be reanalysed
        # unchanged: Set[ProgramUnit] = set()
        # to_analyse: Set[HashedFile] = set()
        unchanged: List[AnalysedFile] = []
        to_analyse: List[HashedFile] = []
        for latest_fpath, latest_hash in latest_file_hashes.items():
            # what happened last time we analysed this file?
            prev_pu = prev_results.get(latest_fpath)
            if (not prev_pu) or prev_pu.file_hash != latest_hash:
                # to_analyse.add(HashedFile(latest_fpath, latest_hash))
                to_analyse.append(HashedFile(latest_fpath, latest_hash))
            else:
                # unchanged.add(prev_pu)
                unchanged.append(prev_pu)
        logger.info(f"{len(unchanged)} already analysed, {len(to_analyse)} to analyse")
        # logger.debug(f"unchanged:\n{[u.fpath for u in unchanged]}")

        return to_analyse, unchanged

    def analyse_file_type(self,
                          fpaths: List[HashedFile],
                          analyser,
                          dict_writer: csv.DictWriter) -> Tuple[List[AnalysedFile], Set[Exception]]:
        """
        Pass the files to the analyser and process the results.

        Returns a list of analysed files and a list of exceptions

        """
        # todo: return a set?
        new_program_units: List[AnalysedFile] = []
        exceptions = set()

        def result_handler(analysis_results):
            for af in analysis_results:
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

    def add_unreferenced_deps(
            self, symbols: Dict[str, Path], all_analysed_files: Dict[Path, AnalysedFile],
            build_tree: Dict[Path, AnalysedFile]):
        """
        Add files to the target tree.

        """

        # todo: list those which are already found, e.g from the new comments deps

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

            # add it
            sub_tree = extract_sub_tree(src_tree=all_analysed_files, key=analysed_fpath)
            build_tree.update(sub_tree)


def gen_symbol_table(all_analysed_files: Dict[Path, AnalysedFile]):
    symbols = dict()
    duplicates = []
    for source_file in all_analysed_files.values():
        for symbol_def in source_file.symbol_defs:
            if symbol_def in symbols:
                duplicates.append(ValueError(
                    f"duplicate symbol '{symbol_def}' defined in {source_file.fpath} "
                    f"already found in {symbols[symbol_def]}"))
                continue
            symbols[symbol_def] = source_file.fpath

    if duplicates:
        err_msg = "\n".join(map(str, duplicates))
        logger.warning(f"Duplicates found while generating symbol table:\n{err_msg}")

    return symbols
import csv
import logging
import multiprocessing
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Iterable

from fab.builder import gen_symbol_table
from fab.dep_tree import AnalysedFile, add_mo_commented_file_deps, extract_sub_tree

from fab.steps import MPMapStep, Step
from fab.util import time_logger, HashedFile, do_checksum

logger = logging.getLogger('fab')


class Analyse(Step):
    """
    This has been done as a single step because the use of mp does not fit the (current) MPStep class
    because we don't have a simple list of artefacts with a function to process one at a time.

    """
    def __init__(self, name):
        super().__init__(name)

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
        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(do_checksum, fpaths)
        else:
            results = [do_checksum(f) for f in fpaths]

        latest_file_hashes: Dict[Path, int] = {fh.fpath: fh.file_hash for fh in results}
        return latest_file_hashes

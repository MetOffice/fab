##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
import configparser
import csv
import hashlib
import subprocess
from collections import namedtuple
from time import perf_counter, sleep
from typing import Dict, List, Set, Tuple

import logging
import multiprocessing
import pickle
from pathlib import Path, PosixPath
import shutil
import sys

from fab.database import SqliteStateDatabase

from fab.tasks.common import Linker, HeaderAnalyser
from fab.tasks.fortran import \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranAnalyser, \
    FortranCompiler, CompiledProgramUnit
from fab.tasks.c import \
    CWorkingState, \
    CPragmaInjector, \
    CPreProcessor, \
    CAnalyser, \
    CCompiler
from fab.tree import ProgramUnit, by_type, extract_sub_tree, EmptyProgramUnit
from fab.util import log_or_dot_finish, do_checksum, file_walk, get_fpaths_by_type, HashedFile

logger = logging.getLogger('fab')
logger.addHandler(logging.StreamHandler(sys.stderr))


def read_config(conf_file):
    config = configparser.ConfigParser(allow_no_value=True)
    configfile = conf_file
    config.read(configfile)

    skip_files = []
    # todo: don't use walrus operator, and set the Python version to [3.6?] in env and setup.
    if skip_files_config := config['settings']['skip-files-list']:
        for line in open(skip_files_config, "rt"):
            skip_files.append(line.strip())

    return config, skip_files


def entry() -> None:
    """
    Entry point for the Fab build tool.
    """
    import fab

    description = 'Flexible build system for scientific software.'

    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    # We add our own help so as to capture as many permutations of how people
    # might ask for help. The default only looks for a subset.
    parser.add_argument('-h', '-help', '--help', action='help',
                        help='Print this help and exit')
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help='Print version identifier and exit')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Increase verbosity (may be specified once '
                             'for moderate and twice for debug verbosity)')
    parser.add_argument('-w', '--workspace', metavar='PATH', type=Path,
                        default=Path.cwd() / 'working',
                        help='Directory for working files.')
    parser.add_argument('--nprocs', action='store', type=int, default=2,
                        choices=range(2, multiprocessing.cpu_count()),
                        help='Provide number of processors available for use,'
                             'default is 2 if not set.')
    parser.add_argument('--skip-if-exists', action="store_true")
    # todo: this won't work with multiple source folders
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build. Accepts a comma separated list.')
    parser.add_argument('conf_file', type=Path, default='config.ini',
                        help='The path of the configuration file')
    arguments = parser.parse_args()

    verbosity_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    verbosity = min(arguments.verbose, 2)
    logger.setLevel(verbosity_levels[verbosity])

    config, skip_files = read_config(arguments.conf_file)
    settings = config['settings']
    flags = config['flags']

    # If not provided, name the exec after the target
    if settings['exec-name'] == '':
        settings['exec-name'] = settings['target']

    application = Fab(workspace=arguments.workspace,
                      target=settings['target'],
                      exec_name=settings['exec-name'],
                      fpp_flags=flags['fpp-flags'],
                      fc_flags=flags['fc-flags'],
                      ld_flags=flags['ld-flags'],
                      n_procs=arguments.nprocs,
                      skip_files=skip_files,
                      unreferenced_deps=settings['unreferenced-dependencies'].split(','))
    application.run(arguments.source.split(','))


class Fab(object):
    def __init__(self,
                 workspace: Path,
                 target: str,
                 exec_name: str,
                 fpp_flags: str,
                 fc_flags: str,
                 ld_flags: str,
                 n_procs: int,
                 stop_on_error: bool = True,  # todo: i think we accidentally stopped using this
                 skip_files=None,
                 unreferenced_deps=None,
                 use_multiprocessing=True):

        self.n_procs = n_procs
        self.target = target
        self._workspace = workspace
        if not workspace.exists():
            workspace.mkdir(parents=True)
        self.skip_files = skip_files or []
        self.fc_flags = fc_flags
        self.unreferenced_deps = unreferenced_deps or []
        self.use_multiprocessing = use_multiprocessing

        self._state = SqliteStateDatabase(workspace)


        # Initialise the required Tasks, providing them with any static
        # properties such as flags to use, workspace location etc
        # TODO: Eventually the tasks may instead access many of these
        # properties via the configuration (at Task runtime, to allow for
        # file-specific overrides?)
        self.fortran_preprocessor = FortranPreProcessor(
            'cpp', ['-traditional-cpp', '-P'] + fpp_flags.split(), workspace)
        self.fortran_analyser = FortranAnalyser(workspace)

        self.fortran_compiler = FortranCompiler(
            'gfortran',
            # '/home/h02/bblay/.conda/envs/sci-fab/bin/mpifort',
            ['-c', '-J', str(self._workspace)] + self.fc_flags.split(),
            self._workspace)

        header_analyser = HeaderAnalyser(workspace)
        c_pragma_injector = CPragmaInjector(workspace)
        c_preprocessor = CPreProcessor(
            'cpp', [], workspace
        )
        c_analyser = CAnalyser(workspace)
        c_compiler = CCompiler(
            'gcc', ['-c'], workspace
        )

        # export OMPI_FC=gfortran
        # https://www.open-mpi.org/faq/?category=mpi-apps#general-build
        # steve thinks we might have to use mpif90
        self.linker = Linker(
            # 'gcc', ['-lc', '-lgfortran'] + ld_flags.split(),
            # 'mpifort', ['-lc', '-lgfortran'] + ld_flags.split(),
            '/home/h02/bblay/.conda/envs/sci-fab/bin/mpifort', ['-lc', '-lgfortran'] + ld_flags.split(),
            workspace, exec_name
        )


    def run(self, source_paths: List[Path]):
        start = perf_counter()

        preprocessed_fortran = self.preprocess(source_paths)

        latest_file_hashes = self.get_latest_checksums(preprocessed_fortran)

        # Analyse ALL files, identifying the program unit name and deps for each file.
        # We get back a flat dict of ProgramUnits, in which the dependency tree is implicit.
        analysed_everything = self.analyse_fortran(latest_file_hashes)

        # Pull out the program units required to build the target.
        target_tree = self.extract_target_tree(analysed_everything)

        # Recursively add any unreferenced dependencies
        # (a fortran routine called without a use statement).
        # This is driven by the config list "unreferenced-dependencies"
        self.add_unreferenced_deps(analysed_everything, target_tree)

        # compile everything we need to build the target
        all_compiled = self.compile(target_tree)

        logger.info("\nlinking")
        self.linker.run(all_compiled)

        logger.warning(f"\nfinished, took {perf_counter() - start}")

        #
        # file_db = FileInfoDatabase(self._state)
        # for file_info in file_db:
        #     print(file_info.filename)
        #     # Where files are generated in the working directory
        #     # by third party tools, we cannot guarantee the hashes
        #     if file_info.filename.match(f'{self._workspace}/*'):
        #         print('    hash: --hidden-- (generated file)')
        #     else:
        #         print(f'    hash: {file_info.adler32}')
        #
        # fortran_db = FortranWorkingState(self._state)
        # for fortran_info in fortran_db:
        #     print(fortran_info.unit.name)
        #     print('    found in: ' + str(fortran_info.unit.found_in))
        #     print('    depends on: ' + str(fortran_info.depends_on))
        #
        # c_db = CWorkingState(self._state)
        # for c_info in c_db:
        #     print(c_info.symbol.name)
        #     print('    found_in: ' + str(c_info.symbol.found_in))
        #     print('    depends on: ' + str(c_info.depends_on))

    def preprocess(self, source_paths):
        start = perf_counter()
        preprocessed_fortran = []
        for source_root in source_paths:
            logger.info(f"\npre-processing {source_root}")
            fpaths = file_walk(source_root, self.skip_files, logger)
            fpaths_by_type = get_fpaths_by_type(fpaths)

            # copy inc files
            # todo: keep folder structure for inc files too?
            self.copy_ancillary_files(fpaths_by_type)

            # Preprocess the source files - output into the workspace folder
            # Note: some files may end up empty, depending on #ifdefs
            preprocessed_fortran.extend(
                self.preprocess_fortran(fpaths_by_type, source_root))

        logger.info(f"\npre-processing {len(source_paths)} folders took {perf_counter() - start}")
        return preprocessed_fortran

    def copy_ancillary_files(self, fpaths_by_type):
        start = perf_counter()
        ancillary_files = fpaths_by_type[".inc"] + fpaths_by_type[".h"]

        # todo: ancillary file types should be in the project config?
        for fpath in ancillary_files:
            logger.debug(f"copying ancillary file {fpath}")
            shutil.copy(fpath, self._workspace)

        logger.info(f"copying {len(ancillary_files)} ancillary files took {perf_counter() - start}")

    def preprocess_fortran(self, fpaths_by_type, source_root):
        logger.info(f"pre-processing {len(fpaths_by_type['.F90'])} files in {source_root}")
        start = perf_counter()

        # create output folder structure
        for fpath in fpaths_by_type[".F90"]:

            # todo: duplicated snippet from run()
            # todo: include source root leaf, e.g src or util.
            rel_fpath = fpath.relative_to(source_root)
            output_fpath = (self._workspace / rel_fpath.with_suffix('.f90'))

            if not output_fpath.parent.exists():
                logger.debug(f"creating output folder {output_fpath.parent}")
                output_fpath.parent.mkdir(parents=True)

        fpaths_with_root = zip(
            fpaths_by_type[".F90"],
            [source_root] * len(fpaths_by_type[".F90"]))

        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                preprocessed_fortran = p.map(
                    self.fortran_preprocessor.run, fpaths_with_root)
        else:
            preprocessed_fortran = [self.fortran_preprocessor.run(f) for f in fpaths_with_root]

        preprocessed_fortran = by_type(preprocessed_fortran)


        # any errors?
        if preprocessed_fortran[Exception]:
            formatted_errors = "\n\n".join(map(str, preprocessed_fortran[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(preprocessed_fortran[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)
        logger.info(f"pre-processing {len(fpaths_by_type['.F90'])} files in {source_root} took {perf_counter() - start}")
        return preprocessed_fortran[PosixPath]

    def get_latest_checksums(self, preprocessed_fortran):
        start = perf_counter()

        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(do_checksum, preprocessed_fortran)
        else:
            results = [do_checksum(f) for f in preprocessed_fortran]

        latest_file_hashes: Dict[Path, int] = {fh.fpath: fh.hash for fh in results}

        logger.info(f"\nhashing {len(latest_file_hashes)} files took {perf_counter() - start}")
        return latest_file_hashes

    def analyse_fortran(self, latest_file_hashes: Dict[Path, int]):
        logger.info("\nanalysing dependencies")
        start = perf_counter()




        # Load analysis results from previous run.
        # Includes the hash of the file when we last analysed it.
        # Note: it would be easy to switch to a database instead of a csv file
        prev_results: Dict[Path, ProgramUnit] = dict()
        try:
            with open(self._workspace / "__analysis.csv", "rt") as csv_file:
                dict_reader = csv.DictReader(csv_file)
                for row in dict_reader:
                    # file no longer there?
                    fpath = Path(row['fpath'])
                    if fpath not in latest_file_hashes:
                        logger.info(f"a file has gone: {row['fpath']}")
                        continue
                    # ok, we have previously analysed this file
                    deps = row['deps'].split(';') if len(row['deps']) else None
                    pu = ProgramUnit(
                        name=row['name'],
                        fpath=fpath,
                        file_hash=int(row['hash']),
                        deps=deps)
                    prev_results[pu.fpath] = pu
            logger.info("loaded previous analysis results")
        except FileNotFoundError:
            logger.info("no previous analysis results")
            pass

        # work out what needs to be reanalysed
        # unchanged: Set[ProgramUnit] = set()
        # to_analyse: Set[HashedFile] = set()
        # sorted for easier debugging
        unchanged: List[ProgramUnit] = []
        to_analyse: List[HashedFile] = []
        latest_file_hashes = sorted(latest_file_hashes.items())
        # for latest_fpath, latest_hash in latest_file_hashes.items():
        for latest_fpath, latest_hash in latest_file_hashes:
            # what happened last time we analysed this file?
            prev_pu = prev_results.get(latest_fpath)
            if (not prev_pu) or prev_pu.hash != latest_hash:
                # to_analyse.add(HashedFile(latest_fpath, latest_hash))
                to_analyse.append(HashedFile(latest_fpath, latest_hash))
            else:
                # unchanged.add(prev_pu)
                unchanged.append(prev_pu)

        logger.info(f"{len(unchanged)} already analysed, {len(to_analyse)} to analyse")

        # todo: use a database here? do a proper pros/cons with the wider team
        # start a new progress file containing anything that's still valid from the last run
        unchanged_rows = (pu.as_dict() for pu in unchanged)

        outfile = open(self._workspace / "__analysis.csv", "wt")
        dict_writer = csv.DictWriter(outfile, fieldnames=['name', 'fpath', 'deps', 'hash'])
        dict_writer.writeheader()
        dict_writer.writerows(unchanged_rows)
        outfile.flush()

        # Analyse everything
        new_program_units: List[ProgramUnit] = []
        exceptions = set()

        def foo(analysis_results):
            for pu in analysis_results:
                if isinstance(pu, EmptyProgramUnit):
                    continue
                elif isinstance(pu, Exception):
                    logger.error(f"\n{pu}")
                    exceptions.add(pu)
                elif isinstance(pu, ProgramUnit):
                    new_program_units.append(pu)
                    dict_writer.writerow(pu.as_dict())
                else:
                    raise RuntimeError(f"Unexpected analysis result type: {pu}")

        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                analysis_results = p.imap_unordered(
                    self.fortran_analyser.run, to_analyse)
                # We cannot refactor out this call, which is in both the if and else
                # because we're using imap. We need to use the iterator before it goes out of scope
                # otherwise it can hang waiting for processes it never got round to create.
                # Todo: Is this an accurate description of the error?
                foo(analysis_results)
        else:
            analysis_results = (self.fortran_analyser.run(a) for a in to_analyse)
            foo(analysis_results)


        outfile.close()




        log_or_dot_finish(logger)
        logger.info(f"analysis took {perf_counter() - start}")


        # Errors?
        if exceptions:
            ex_str = "\n\n".join(map(str, exceptions))
            logger.error(f"{len(exceptions)} errors analysing fortran")
            exit(1)

        # Put the program units into a dict, keyed by name.
        # The dependency tree is implicit, since deps are keys into the dict.
        tree = dict()
        for p in unchanged + new_program_units:
            tree[p.name] = p

        return tree

    def extract_target_tree(self, analysed_everything):
        logger.info("\nextracting target sub tree")
        target_tree, missing = extract_sub_tree(analysed_everything, self.target, verbose=False)
        if missing:
            logger.warning(f"missing deps {missing}")
        else:
            logger.info("no missing deps")
        logger.info(f"tree size (all files) {len(analysed_everything)}")
        logger.info(f"tree size (target '{self.target}') {len(target_tree)}")
        return target_tree

    def add_unreferenced_deps(self, analysed_everything, target_tree):
        logger.info(f"Adding unreferenced dependencies")

        def foo(dep):
            pu = analysed_everything.get(dep)
            if not pu:
                if dep != "mpi":  # todo: remove this if?
                    logger.warning(f"couldn't find dep '{dep}'")
                return

            if dep not in target_tree:
                logger.debug(f"Adding unreferenced dependency {dep}")
                target_tree[dep] = pu

            for sub in pu.deps:
                foo(sub)

        for dep in self.unreferenced_deps:
            foo(dep)

    def compile(self, target_tree):
        logger.info(f"\ncompiling {len(target_tree)} files")
        start = perf_counter()


        to_compile = set(target_tree.values())
        all_compiled = []  # todo: use set
        already_compiled_names = set()
        per_pass = []
        while to_compile:

            # find what to compile next
            compile_next = []
            for pu in to_compile:
                # all deps ready?
                can_compile = True
                for dep in pu.deps:
                    if dep not in already_compiled_names:
                        can_compile = False
                        break
                if can_compile:
                    compile_next.append(pu)

            logger.debug(f"compiling {len(compile_next)} of {len(to_compile)} remaining files")

            if self.use_multiprocessing:
                with multiprocessing.Pool(self.n_procs) as p:
                    this_pass = p.map(self.fortran_compiler.run, compile_next)
            else:
                this_pass = [self.fortran_compiler.run(f) for f in compile_next]

            # this_pass = []
            # for f in compile_next:
            #     this_pass.append(self.fortran_compiler.run(f))

            # nothing compiled?
            compiled_this_pass = by_type(this_pass)[CompiledProgramUnit]
            per_pass.append(len(compiled_this_pass))
            if len(compiled_this_pass) == 0:
                logger.error("nothing compiled this pass")
                break

            # todo: any errors?

            # remove compiled files from list
            logger.debug(f"compiled {len(compiled_this_pass)} files")

            # ProgramUnit - not the same as passed in, due to mp copying
            compiled_names = {i.program_unit.name for i in compiled_this_pass}
            logger.debug(f"compiled_names {compiled_names}")
            all_compiled.extend(compiled_this_pass)
            already_compiled_names.update(compiled_names)

            # to_compile.difference_update(compiled_program_units)
            to_compile = list(filter(lambda pu: pu.name not in compiled_names, to_compile))
        if to_compile:
            logger.warning(f"there were still {len(to_compile)} files left to compile")
            for pu in to_compile:
                logger.warning(pu.name)

        log_or_dot_finish(logger)
        logger.debug(f"compiled per pass {per_pass}")
        logger.info(f"total compiled {sum(per_pass)}")
        logger.info(f"compilation took {perf_counter() - start}")
        return all_compiled

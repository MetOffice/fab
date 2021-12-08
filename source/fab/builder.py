##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
import configparser
import csv
import os
from time import perf_counter
from typing import Dict, List

import logging
import multiprocessing
from pathlib import Path, PosixPath
import shutil
import sys

from fab.constants import OUTPUT_ROOT, SOURCE_ROOT
from fab.database import SqliteStateDatabase
from fab.tasks import Task

from fab.tasks.common import Linker, HeaderAnalyser
from fab.tasks.fortran import \
    FortranAnalyser, \
    FortranCompiler, CompiledProgramUnit
from fab.tasks.c import \
    CPragmaInjector, \
    CPreProcessor, \
    CAnalyser, \
    CCompiler
from fab.dep_tree import ProgramUnit, by_type, extract_sub_tree, EmptyProgramUnit
from fab.util import log_or_dot_finish, do_checksum, file_walk, get_fpaths_by_type, HashedFile, ensure_output_folder

logger = logging.getLogger('fab')
logger.addHandler(logging.StreamHandler(sys.stderr))


def read_config(conf_file):
    """
    Read the config file.

    Adds processed attributes from the lists:
     - skip_files
     - unreferenced_deps
     - include_paths

    Relative include paths are relative to the location of each file being processed.
    Absolute include paths (beggining with /) are relative to the workspace root.
    """
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(conf_file)

    config.skip_files = []
    # todo: don't use walrus operator, and set the Python version to [3.6?] in env and setup.
    if skip_files_config := config['settings']['skip-files-list']:
        for line in open(skip_files_config, "rt"):
            config.skip_files.append(line.strip())

    config.unreferenced_deps = sorted(filter(
        lambda i: bool(i),
        [i.strip() for i in config['settings']['unreferenced-dependencies'].split(',')]))

    # config.src_paths = [Path(os.path.expanduser(i)) for i in config['settings']['src-paths'].split(',')]
    config.include_paths = [Path(os.path.expanduser(i)) for i in config['settings']['include-paths'].split(',')]

    return config


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

    config, skip_files, unreferenced_deps = read_config(arguments.conf_file)
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
                      unreferenced_deps=unreferenced_deps)
    application.run(arguments.source.split(','))


class Fab(object):
    def __init__(self,
                 include_paths: List[Path],
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
                 use_multiprocessing=True,
                 debug_skip=False,
    ):

        # self.source_paths = source_paths
        self.n_procs = n_procs
        self.target = target
        self._workspace = workspace
        self.skip_files = skip_files or []
        self.fc_flags = fc_flags
        self.unreferenced_deps = unreferenced_deps or []
        self.use_multiprocessing = use_multiprocessing
        # self.include_paths = include_paths or []

        if not workspace.exists():
            workspace.mkdir(parents=True)
        if not (workspace / OUTPUT_ROOT).exists():
            (workspace / OUTPUT_ROOT).mkdir()

        self._state = SqliteStateDatabase(workspace)


        # Initialise the required Tasks, providing them with any static
        # properties such as flags to use, workspace location etc
        # TODO: Eventually the tasks may instead access many of these
        # properties via the configuration (at Task runtime, to allow for
        # file-specific overrides?)
        # self.fortran_preprocessor = FortranPreProcessor(
        self.fortran_preprocessor = CPreProcessor(
            preprocessor='cpp',
            flags=['-traditional-cpp', '-P'] + fpp_flags.split(),
            workspace=workspace,
            include_paths=include_paths,
            output_suffix=".f90",
            debug_skip=debug_skip)
        self.fortran_analyser = FortranAnalyser(workspace)

        self.fortran_compiler = FortranCompiler(
            'gfortran',
            # '/home/h02/bblay/.conda/envs/sci-fab/bin/mpifort',
            ['-c', '-J', str(self._workspace)] + self.fc_flags.split(),
            self._workspace)

        header_analyser = HeaderAnalyser(workspace)
        c_pragma_injector = CPragmaInjector(workspace)
        self.c_preprocessor = CPreProcessor(
            preprocessor='cpp',
            flags=[],
            workspace=workspace,
            output_suffix=".c",
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


    def run(self):
        start = perf_counter()

        all_source = self.walk_source_folder()

        # Copy ancillary files, such as Fortran inc and C files
        self.copy_ancillary_files(all_source)

        # Before calling the C pre-processor, we mark the include regions
        # so we can tell if they are system or user includes after preprocessing.
        pragmad_c = self.c_pragmas(all_source[".c"])

        preprocessed_c = self.preprocess(fpaths=pragmad_c, preprocessor=self.c_preprocessor)
        preprocessed_fortran = self.preprocess(
            fpaths=all_source[".F90"] + all_source[".f90"], preprocessor=self.fortran_preprocessor)


        exit(0)


        # Analyse ALL files, identifying the program unit name and deps for each file.
        # We get back a flat dict of ProgramUnits, in which the dependency tree is implicit.
        latest_file_hashes = self.get_latest_checksums(preprocessed_fortran)
        analysed_everything = self.analyse_fortran(latest_file_hashes)

        # Pull out the program units required to build the target.
        # with cProfile.Profile() as profiler:
        target_tree = self.extract_target_tree(analysed_everything)
        # profiler.dump_stats('extract_target_tree.pstats')

        # Recursively add any unreferenced dependencies
        # (a fortran routine called without a use statement).
        # This is driven by the config list "unreferenced-dependencies"
        self.add_unreferenced_deps(analysed_everything, target_tree)

        self.validate_target_tree(target_tree)

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


    def walk_source_folder(self) -> Dict[str, List[Path]]:
        """
        Get all files in the folder and subfolders.

        Returns a dict[source_folder][extension] = file_list
        """
        start = perf_counter()
        # all_source = dict()
        paths = file_walk(self._workspace / SOURCE_ROOT, self.skip_files, logger)
        if not paths:
            logger.warning(f"no source files found")
            exit(1)
        fpaths_by_type = get_fpaths_by_type(paths)
        logger.info(f"walking source folder took {perf_counter() - start}")
        return fpaths_by_type

    # todo: multiprocessing
    # todo: ancillary file types should be in the project config?
    def copy_ancillary_files(self, files_by_type: Dict[str, List[Path]]):
        """
        Copy inc and .h files into the workspace.

        Required for preprocessing
        Copies everything to the workspace root.
        Checks for name clash.

        """
        start = perf_counter()

        # inc files all go in the root - they're going to be removed altogether, soon
        inc_copied = set()
        for fpath in files_by_type[".inc"]:
            logger.debug(f"copying inc file {fpath}")
            if fpath.name in inc_copied:
                logger.error(f"name clash for ancillary file: {fpath}")
                exit(1)

            shutil.copy(fpath, self._workspace / OUTPUT_ROOT)
            inc_copied.add(fpath.name)

        # header files go into the same folder structure they came from
        for fpath in files_by_type[".h"]:
            rel_path = fpath.relative_to(self._workspace / SOURCE_ROOT)
            dest_path = self._workspace / OUTPUT_ROOT / rel_path

            ensure_output_folder(fpath=dest_path, workspace=self._workspace)
            logger.debug(f"copying header file {fpath} to {dest_path}")
            shutil.copy(fpath, dest_path)

        logger.info(f"copying ancillary files took {perf_counter() - start}")

    def c_pragmas(self, fpaths: List[Path]):
        start = perf_counter()

        pragmad_c = []

        return pragmad_c


    def preprocess(self, fpaths, preprocessor: Task):
        start = perf_counter()

        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(preprocessor.run, fpaths)
        else:
            results = [preprocessor.run(f) for f in fpaths]
        results = by_type(results)

        # any errors?
        if results[Exception]:
            formatted_errors = "\n\n".join(map(str, results[Exception]))
            raise Exception(
                f"{formatted_errors}"
                f"\n\n{len(results[Exception])} "
                f"Error(s) found during preprocessing: "
            )

        log_or_dot_finish(logger)
        logger.info(f"pre-processing {preprocessor.__class__.__name__} took {perf_counter() - start}")
        return results[PosixPath]

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
        unchanged: List[ProgramUnit] = []
        to_analyse: List[HashedFile] = []
        latest_file_hashes = sorted(latest_file_hashes.items())  # sorted for easier debugging
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
        logger.debug(f"{[u.name for u in unchanged]}")

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

        def process_analysis_results(analysis_results):
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
                process_analysis_results(analysis_results)
        else:
            analysis_results = (self.fortran_analyser.run(a) for a in to_analyse)
            process_analysis_results(analysis_results)


        outfile.close()




        log_or_dot_finish(logger)
        logger.info(f"analysis took {perf_counter() - start}")


        # Errors?
        if exceptions:
            ex_str = "\n\n".join(map(str, exceptions))
            logger.error(f"{len(exceptions)} errors analysing fortran")
            # exit(1)

        # Put the program units into a dict, keyed by name.
        # The dependency tree is implicit, since deps are keys into the dict.
        tree = dict()
        for p in unchanged + new_program_units:
            tree[p.name] = p

        return tree

    def extract_target_tree(self, analysed_everything):
        logger.info("\nextracting target sub tree")
        start = perf_counter()

        target_tree, missing = extract_sub_tree(analysed_everything, self.target, verbose=False)
        if missing:
            logger.warning(f"missing deps {missing}")
        else:
            logger.info("no missing deps")

        logger.info(f"extracting target tree took {perf_counter() - start}")
        logger.info(f"tree size (all files) {len(analysed_everything)}")
        logger.info(f"tree size (target '{self.target}') {len(target_tree)}")
        return target_tree

    def add_unreferenced_deps(self, analysed_everything, target_tree):
        if not self.unreferenced_deps:
            return
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

            logger.info(f"checking {len(to_compile)} program units")

            # find what to compile next
            compile_next = []
            not_ready = {}
            for pu in to_compile:
                # all deps ready?
                unfulfilled = [dep for dep in pu.deps if dep not in already_compiled_names]
                if not unfulfilled:
                    compile_next.append(pu)
                else:
                    not_ready[pu.name] = unfulfilled

            for pu_name, deps in not_ready.items():
                logger.info(f"not ready to compile {pu_name}, needs {', '.join(deps)}")
            logger.info(f"compiling {len(compile_next)} of {len(to_compile)} remaining files")

            # report if unable to compile everything
            if len(to_compile) and not compile_next:
                all_unfulfilled = set()
                for values in not_ready.values():
                    all_unfulfilled = all_unfulfilled.union(values)
                logger.error(f"All unfulfilled deps: {', '.join(all_unfulfilled)}")
                exit(1)

            if self.use_multiprocessing:
                with multiprocessing.Pool(self.n_procs) as p:
                    this_pass = p.map(self.fortran_compiler.run, compile_next)
            else:
                this_pass = [self.fortran_compiler.run(f) for f in compile_next]


            # any errors?
            errors = []
            for i in this_pass:
                if isinstance(i, Exception):
                    errors.append(i)
            logger.error(f"\nThere were {len(errors)} compile errors this pass\n\n")
            if errors:
                err_str = "\n\n".join(map(str, errors))
                logger.error(err_str)
                exit(1)

            # check what we did compile
            compiled_this_pass = by_type(this_pass)[CompiledProgramUnit]
            per_pass.append(len(compiled_this_pass))
            if len(compiled_this_pass) == 0:
                logger.error("nothing compiled this pass")
                break

            # remove compiled files from list
            logger.debug(f"compiled {len(compiled_this_pass)} files")

            # ProgramUnit - not the same as passed in, due to mp copying
            compiled_names = {i.program_unit.name for i in compiled_this_pass}
            logger.debug(f"compiled_names {compiled_names}")
            all_compiled.extend(compiled_this_pass)
            already_compiled_names.update(compiled_names)

            # remove from remaining to compile
            to_compile = list(filter(lambda pu: pu.name not in compiled_names, to_compile))

        log_or_dot_finish(logger)
        logger.debug(f"compiled per pass {per_pass}")
        logger.info(f"total compiled {sum(per_pass)}")
        logger.info(f"compilation took {perf_counter() - start}")

        if to_compile:
            logger.debug(f"there were still {len(to_compile)} files left to compile")
            for pu in to_compile:
                logger.debug(pu.name)
            logger.error(f"there were still {len(to_compile)} files left to compile")
            exit(1)

        return all_compiled

    def validate_target_tree(self, target_tree):
        """If any dep is not in the tree, then it's unknown code and we won't be able to compile."""
        missing = set()
        for pu in target_tree.values():
            missing = missing.union(
                [dep for dep in pu.deps if dep not in target_tree])

        if missing:
            logger.error(f"Unknown dependencies, cannot build: {', '.join(sorted(missing))}")
            exit(1)




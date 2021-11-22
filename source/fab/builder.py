##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
import configparser
from time import perf_counter, sleep
from typing import Dict, List

import logging
import multiprocessing
import pickle
from pathlib import Path
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
from fab.source_tree import get_fpaths_by_type, file_walk
from fab.tree import ProgramUnit, by_type, extract_sub_tree
from fab.util import log_or_dot_finish

logger = logging.getLogger('fab')
logger.addHandler(logging.StreamHandler(sys.stderr))


def read_config(conf_file):
    config = configparser.ConfigParser(allow_no_value=True)
    configfile = conf_file
    config.read(configfile)

    skip_files = []
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
                      skip_if_exists=arguments.skip_if_exists,
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
                 stop_on_error: bool = True,
                 skip_files=None,
                 skip_if_exists=False,
                 unreferenced_deps=None):

        self.n_procs = n_procs
        self.target = target
        self._workspace = workspace
        if not workspace.exists():
            workspace.mkdir(parents=True)
        self.skip_files = skip_files or []
        self.fc_flags = fc_flags
        self.skip_if_exists = skip_if_exists
        self.unreferenced_deps = unreferenced_deps or []

        self._state = SqliteStateDatabase(workspace)


        # Initialise the required Tasks, providing them with any static
        # properties such as flags to use, workspace location etc
        # TODO: Eventually the tasks may instead access many of these
        # properties via the configuration (at Task runtime, to allow for
        # file-specific overrides?)
        self.fortran_preprocessor = FortranPreProcessor(
            'cpp', ['-traditional-cpp', '-P'] + fpp_flags.split(), workspace,
            skip_if_exists=skip_if_exists
        )
        self.fortran_analyser = FortranAnalyser(workspace)

        self.fortran_compiler = FortranCompiler(
            'gfortran',
            # '/home/h02/bblay/.conda/envs/sci-fab/bin/mpifort',
            ['-c', '-J', str(self._workspace)] + self.fc_flags.split(),
            self._workspace, skip_if_exists=self.skip_if_exists)

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

        # walk the source folder
        preprocessed_fortran = []
        for source_root in source_paths:
            fpaths = file_walk(source_root, self.skip_files, logger)

            fpaths_by_type = get_fpaths_by_type(fpaths)

            # todo: keep folder structure for inc files too?
            self.copy_ancillary_files(fpaths_by_type)

            preprocessed_fortran.extend(
                self.preprocess(fpaths_by_type, source_root))


        # analyse ALL files to get deps
        analysed_fortran = self.analyse_fortran(preprocessed_fortran)

        # pull out just those required to build the target
        logger.info("\nextracting target sub tree")
        target_tree, missing = extract_sub_tree(analysed_fortran, self.target, verbose=False)
        if missing:
            logger.warning(f"missing deps {missing}")
        else:
            logger.info("no missing deps")

        logger.info(f"tree size (all files) {len(analysed_fortran)}")
        logger.info(f"tree size (target '{self.target}') {len(target_tree)}")

        # Add any unreferenced dependencies
        # (where a fortran routine is called without a use statement).
        def foo(dep):
            pu = analysed_fortran.get(dep)

            if not pu:
                logger.warning(f"couldn't find dep {dep}")
                return

            if dep not in target_tree:
                logger.warning(f"Adding unreferenced dependency {dep}")
                target_tree[dep] = pu

            for sub in pu.deps:
                foo(sub)
        for dep in self.unreferenced_deps:
            foo(dep)

        #
        all_compiled = self.compile(target_tree)

        logger.info("\nlinking")
        self.linker.run(all_compiled)

        logger.warning("\nfinished")


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


    def copy_ancillary_files(self, fpaths_by_type):
        logger.info(f"\ncopying {len(fpaths_by_type['.inc'])} ancillary files")
        for fpath in fpaths_by_type[".inc"]:
            logger.debug(f"copying ancillary file {fpath}")
            shutil.copy(fpath, self._workspace)

    def preprocess(self, fpaths_by_type, source_root):
        logger.info(f"\npreprocessing {source_root}")
        start = perf_counter()

        # create output folder structure
        for fpath in fpaths_by_type[".F90"]:

            # todo: duplicated snippet from run()
            rel_fpath = fpath.relative_to(source_root)
            output_fpath = (self._workspace / rel_fpath.with_suffix('.f90'))

            if not output_fpath.parent.exists():
                logger.debug(f"creating output folder {output_fpath.parent}")
                output_fpath.parent.mkdir(parents=True)

        fpaths_with_root = zip(
            fpaths_by_type[".F90"],
            [source_root] * len(fpaths_by_type[".F90"]))

        with multiprocessing.Pool(self.n_procs) as p:
            # preprocessed_fortran = p.map(  # 2.3s / 3
                # self.fortran_preprocessor.run, fpaths_by_type[".F90"])
            preprocessed_fortran = p.starmap(  # 2.3s / 3
                self.fortran_preprocessor.run, fpaths_with_root)

            preprocessed_fortran = list(preprocessed_fortran)

        log_or_dot_finish(logger)
        logger.info(f"preprocess took {perf_counter() - start}")
        return preprocessed_fortran

    def analyse_fortran(self, preprocessed_fortran):
        logger.info("\nanalysing dependencies")
        start = perf_counter()

        # Load analysis results from previous run.
        # For now, just a pickle.
        # todo: We plan to save to a data store as we go, for interrupted runs
        analysis_pickle = self._workspace / "__analysis_f.pickle"
        if analysis_pickle.exists():
            logger.debug("loading fortran analysis from pickle")
            with open(analysis_pickle, "rb") as infile:
                program_units = pickle.load(infile)
        else:
            with multiprocessing.Pool(self.n_procs) as p:
                program_units = p.map(
                    self.fortran_analyser.run, preprocessed_fortran)

            # program_units = []
            # for ppf in preprocessed_fortran:
            #     program_units.append(self.fortran_analyser.run(ppf))

            program_units = by_type(program_units)
            if program_units[Exception]:
                logger.error("there were errors analysing fortran:",
                             program_units[Exception])
                raise Exception("there were errors analysing fortran:",
                                program_units[Exception])

            logger.debug("writing fortran analysis to pickle")
            with open(analysis_pickle, "wb") as outfile:
                pickle.dump(program_units, outfile)

        tree = dict()
        for p in program_units[ProgramUnit]:
            tree[p.name] = p

        log_or_dot_finish(logger)
        logger.info(f"analysis took {perf_counter() - start}")
        return tree

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

            with multiprocessing.Pool(self.n_procs) as p:
                this_pass = p.map(self.fortran_compiler.run, compile_next)

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

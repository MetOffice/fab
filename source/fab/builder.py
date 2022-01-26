##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
import csv
import os
import warnings
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from time import perf_counter
from typing import Dict, List, Tuple, Set, Iterable

import logging
import multiprocessing
from pathlib import Path

from fab import steps
from fab.config_sketch import ConfigSketch
from fab.constants import BUILD_OUTPUT

from fab.tasks.fortran import \
    FortranAnalyser, \
    FortranCompiler
from fab.tasks.c import \
    CAnalyser, \
    CCompiler
from fab.dep_tree import AnalysedFile, by_type, extract_sub_tree, EmptySourceFile, add_mo_commented_file_deps, \
    validate_build_tree
from fab.util import log_or_dot_finish, do_checksum, HashedFile, \
    time_logger, CompiledFile


logger = logging.getLogger('fab')

runtime_str = datetime.now().strftime("%Y%m%d_%H%M%S")


# todo: uncomment and get this working again
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

    # todo: uncomment and get this working again
    # config, skip_files, unreferenced_deps = read_config(arguments.conf_file)
    # settings = config['settings']
    # flags = config['flags']

    # If not provided, name the exec after the target
    # if settings['exec-name'] == '':
    #     settings['exec-name'] = settings['target']

    # application = Fab(workspace=arguments.workspace,
    #                   target=settings['target'],
    #                   exec_name=settings['exec-name'],
    #                   fpp_flags=flags['fpp-flags'],
    #                   fc_flags=flags['fc-flags'],
    #                   ld_flags=flags['ld-flags'],
    #                   n_procs=arguments.nprocs,
    #                   skip_files=skip_files,
    #                   unreferenced_deps=unreferenced_deps)
    # application.run(arguments.source.split(','))


class Build(object):
    def __init__(self,
                 # workspace: Path,
                 config: ConfigSketch,
                 n_procs: int,
                 use_multiprocessing=True,
                 debug_skip=False,
                 dump_source_tree=False):

        # self.root_symbol = config.root_symbol
        # self._workspace = workspace
        self.config = config
        self.unreferenced_deps: List[str] = config.unreferenced_dependencies or []

        self.n_procs = n_procs
        self.use_multiprocessing = use_multiprocessing
        self.dump_source_tree = dump_source_tree

        if not config.workspace.exists():
            config.workspace.mkdir(parents=True)
        if not (config.workspace / BUILD_OUTPUT).exists():
            (config.workspace / BUILD_OUTPUT).mkdir()

        self.fortran_compiler = FortranCompiler(
            # todo: make configurable
            compiler=[
                os.path.expanduser('~/.conda/envs/sci-fab/bin/gfortran'),
                '-c',
                '-J', str(config.workspace / BUILD_OUTPUT),  # .mod file output and include folder
            ],

            # '/home/h02/bblay/.conda/envs/sci-fab/bin/mpifort',

            flags=config.fc_flag_config,
            debug_skip=debug_skip,
        )

        self.c_compiler = CCompiler(
            compiler=['gcc', '-c', '-std=c99'],  # why std?
            flags=config.cc_flag_config,
            workspace=config.workspace,
        )

        # for when fparser2 cannot process a file but gfortran can compile it
        self.special_measure_analysis_results = config.special_measure_analysis_results

    def run(self):

        logger.info(f"{datetime.now()}")
        logger.info(f"n_procs = {steps.n_procs}")

        artefacts = dict()
        for step in self.config.steps:
            with time_logger(step.name):
                step.run(artefacts)

        # compile everything we need to build the target
        # todo: output into the folder structures to avoid name clash
        with time_logger("compiling"):
            all_compiled = self.compile(artefacts['build_tree'])

        with time_logger("linking"):
            self.config.linker.run(compiled_files=all_compiled)

    def compile(self, build_tree):

        c_files: Set[AnalysedFile] = {af for af in build_tree.values() if af.fpath.suffix == ".c"}  # todo: filter?
        compiled_c = self.compile_c(c_files)

        fortran_files: Set[AnalysedFile] = {af for af in build_tree.values() if af.fpath.suffix == ".f90"}
        compiled_fortran = self.compile_fortran(fortran_files)

        all_compiled: Set[CompiledFile] = set(compiled_c + compiled_fortran)
        return all_compiled

    def compile_c(self, to_compile: Set[AnalysedFile]):
        logger.info(f"compiling {len(to_compile)} c files")
        if self.use_multiprocessing:
            with multiprocessing.Pool(self.n_procs) as p:
                results = p.map(self.c_compiler.run, to_compile)
        else:
            results = [self.c_compiler.run(c) for c in to_compile]

        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            err_msg = '\n\n'.join(map(str, errors))
            logger.error(f"There were {len(errors)} errors compiling {len(to_compile)} c files:\n{err_msg}")
            exit(1)

        compiled_c = [result for result in results if isinstance(result, CompiledFile)]
        logger.info(f"compiled {len(compiled_c)} c files")
        return compiled_c

    def compile_fortran(self, to_compile: Set[AnalysedFile]):
        logger.info(f"\ncompiling {len(to_compile)} fortran files")
        start = perf_counter()

        # the full return data
        all_compiled: List[CompiledFile] = []  # todo: use set

        # a quick lookup
        already_compiled_files = set()

        # Record which fortran file created which .o file in case of name clash.
        # This is because we currently put all the .o files in one big folder.
        name_clash_check = {}

        per_pass = []
        while to_compile:

            # find what to compile next
            compile_next = []
            not_ready = {}
            for af in to_compile:
                # all deps ready?
                unfulfilled = [dep for dep in af.file_deps if dep not in already_compiled_files and dep.suffix == '.f90']
                if not unfulfilled:
                    compile_next.append(af)
                else:
                    not_ready[af.fpath] = unfulfilled

            logger.info(f"\ncompiling {len(compile_next)} of {len(to_compile)} remaining files")

            # report if unable to compile everything
            if len(to_compile) and not compile_next:
                all_unfulfilled = set()
                for values in not_ready.values():
                    all_unfulfilled = all_unfulfilled.union(values)
                logger.error(f"All unfulfilled deps: {', '.join(map(str, all_unfulfilled))}")
                exit(1)

            if self.use_multiprocessing:
                with multiprocessing.Pool(self.n_procs) as p:
                    this_pass = p.map(self.fortran_compiler.run, compile_next)
            else:
                this_pass = [self.fortran_compiler.run(f) for f in compile_next]

            # any errors?
            # todo: improve by_type pattern to handle all exceptions as one
            errors = []
            for i in this_pass:
                if isinstance(i, Exception):
                    errors.append(i)
            if len(errors):
                logger.error(f"\nThere were {len(errors)} compile errors this pass\n\n")
            if errors:
                err_str = "\n\n".join(map(str, errors))
                logger.error(err_str)
                exit(1)

            # check what we did compile
            compiled_this_pass: Set[CompiledFile] = by_type(this_pass)[CompiledFile]
            per_pass.append(len(compiled_this_pass))
            if len(compiled_this_pass) == 0:
                logger.error("nothing compiled this pass")
                break

            # check for name clash - had another file already compiled to this output file?
            # this is much less likely to happen now we're creating the object files in the source folders,
            # but still possible - todo: should we remove this check?
            for compiled_file in compiled_this_pass:
                output_file = compiled_file.output_fpath
                if output_file in name_clash_check:
                    raise RuntimeError(
                        f"Filename clash after compiling {compiled_file.analysed_file.fpath}: "
                        f"output file {output_file} already created from {name_clash_check[output_file]}")
                name_clash_check[output_file] = compiled_file.analysed_file.fpath

            # remove compiled files from list
            logger.debug(f"compiled {len(compiled_this_pass)} files")

            # ProgramUnit - not the same as passed in, due to mp copying
            compiled_fpaths = {i.analysed_file.fpath for i in compiled_this_pass}
            # logger.debug(f"compiled_names {compiled_fpaths}")
            all_compiled.extend(compiled_this_pass)
            already_compiled_files.update(compiled_fpaths)

            # remove from remaining to compile
            to_compile = list(filter(lambda af: af.fpath not in compiled_fpaths, to_compile))

        log_or_dot_finish(logger)
        logger.debug(f"compiled per pass {per_pass}")
        logger.info(f"total fortran compiled {sum(per_pass)}")
        logger.info(f"compiling fortran took {perf_counter() - start}\n")

        if to_compile:
            logger.debug(f"there were still {len(to_compile)} files left to compile")
            for af in to_compile:
                logger.debug(af.fpath)
            logger.error(f"there were still {len(to_compile)} files left to compile")
            exit(1)

        return all_compiled

    # def validate_build_tree(self, target_tree):
    #     """
    #     If any dep is not in the tree, then it's unknown code and we won't be able to compile.
    #
    #     This was added as a helpful message when building the unreferenced dependencies list.
    #     """
    #     missing = set()
    #     for pu in target_tree.values():
    #         missing = missing.union(
    #             [str(file_dep) for file_dep in pu.file_deps if file_dep not in target_tree])
    #
    #     if missing:
    #         logger.error(f"Unknown dependencies, expecting build to fail: {', '.join(sorted(missing))}")
    #         # exit(1)


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


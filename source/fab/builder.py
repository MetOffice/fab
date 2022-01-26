##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
from datetime import datetime
from typing import Dict, List
import logging
import multiprocessing
from pathlib import Path

from fab import steps
from fab.config_sketch import ConfigSketch
from fab.constants import BUILD_OUTPUT

from fab.dep_tree import AnalysedFile
from fab.util import time_logger


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

        self.config = config
        self.unreferenced_deps: List[str] = config.unreferenced_dependencies or []

        self.n_procs = n_procs
        self.use_multiprocessing = use_multiprocessing
        self.dump_source_tree = dump_source_tree

        if not config.workspace.exists():
            config.workspace.mkdir(parents=True)
        if not (config.workspace / BUILD_OUTPUT).exists():
            (config.workspace / BUILD_OUTPUT).mkdir()

        # for when fparser2 cannot process a file but gfortran can compile it
        self.special_measure_analysis_results = config.special_measure_analysis_results

    def run(self):

        logger.info(f"{datetime.now()}")
        logger.info(f"n_procs = {steps.n_procs}")

        artefacts = dict()
        for step in self.config.steps:
            with time_logger(step.name):
                step.run(artefacts)

        with time_logger("linking"):
            self.config.linker.run(compiled_files=artefacts['compiled_c'] + artefacts['compiled_fortran'])


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

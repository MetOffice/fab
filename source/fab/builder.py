##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import argparse
import configparser
import logging
import multiprocessing
from pathlib import Path
import shutil
import sys

from fab.database import SqliteStateDatabase, FileInfoDatabase
from fab.artifact import \
    Artifact, \
    FortranSource, \
    CSource, \
    CHeader, \
    BinaryObject, \
    Seen, \
    HeadersAnalysed, \
    Modified, \
    Raw, \
    Analysed, \
    Compiled
from fab.tasks.common import Linker, HeaderAnalyser
from fab.tasks.fortran import \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranAnalyser, \
    FortranCompiler
from fab.tasks.c import \
    CWorkingState, \
    CPragmaInjector, \
    CPreProcessor, \
    CAnalyser, \
    CCompiler
from fab.source_tree import \
    TreeDescent, \
    SourceVisitor
from fab.queue import QueueManager
from fab.engine import Engine, PathMap


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
    parser.add_argument('--stop-on-error', action="store_true")
    parser.add_argument('--skip-if-exists', action="store_true")
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build')
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
                      stop_on_error=arguments.stop_on_error,
                      skip_files=skip_files,
                      skip_if_exists=arguments.skip_if_exists)
    application.run(arguments.source)


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
                 skip_if_exists=False):
        self.skip_files = skip_files or []

        self._workspace = workspace
        if not workspace.exists():
            workspace.mkdir(parents=True)

        self._state = SqliteStateDatabase(workspace)

        # Path maps tell the engine what filetype and starting state
        # the Artifacts representing any files encountered by the
        # initial descent should have
        path_maps = [
            PathMap(r'.*\.f90', FortranSource, Raw),
            PathMap(r'.*\.F90', FortranSource, Seen),
            PathMap(r'.*\.c', CSource, Seen),
            PathMap(r'.*\.h', CHeader, Seen),
        ]

        # Initialise the required Tasks, providing them with any static
        # properties such as flags to use, workspace location etc
        # TODO: Eventually the tasks may instead access many of these
        # properties via the configuration (at Task runtime, to allow for
        # file-specific overrides?)
        fortran_preprocessor = FortranPreProcessor(
            'cpp', ['-traditional-cpp', '-P'] + fpp_flags.split(), workspace,
            skip_if_exists=skip_if_exists
        )
        fortran_analyser = FortranAnalyser(workspace)
        fortran_compiler = FortranCompiler(
            'gfortran',
            ['-c', '-J', str(workspace)] + fc_flags.split(), workspace,
            skip_if_exists=skip_if_exists
        )

        header_analyser = HeaderAnalyser(workspace)
        c_pragma_injector = CPragmaInjector(workspace)
        c_preprocessor = CPreProcessor(
            'cpp', [], workspace
        )
        c_analyser = CAnalyser(workspace)
        c_compiler = CCompiler(
            'gcc', ['-c'], workspace
        )

        linker = Linker(
            'gcc', ['-lc', '-lgfortran'] + ld_flags.split(),
            workspace, exec_name
        )

        # The Task map tells the engine what Task it should be using
        # to deal with Artifacts depending on their type and state
        task_map = {
            (FortranSource, Seen): fortran_preprocessor,
            (FortranSource, Raw): fortran_analyser,
            (FortranSource, Analysed): fortran_compiler,
            (CSource, Seen): header_analyser,
            (CHeader, Seen): header_analyser,
            (CSource, HeadersAnalysed): c_pragma_injector,
            (CHeader, HeadersAnalysed): c_pragma_injector,
            (CSource, Modified): c_preprocessor,
            (CSource, Raw): c_analyser,
            (CSource, Analysed): c_compiler,
            (BinaryObject, Compiled): linker,
        }

        engine = Engine(workspace,
                        target,
                        path_maps,
                        task_map)
        self._queue = QueueManager(n_procs - 1, engine, stop_on_error)

    def _extend_queue(self, artifact: Artifact) -> None:
        if str(artifact.location.parts[-1]) in self.skip_files:
            logger.warning(f"skipping {artifact.location}")
            return
        self._queue.add_to_queue(artifact)

    def run(self, source: Path):

        self._queue.run()

        # first, we need to copy over all the ancillary files
        # TODO: inc files are being removed, so this step should eventually be removed
        def copy_acillary_file(artifact):
            if str(artifact.location).endswith(".inc"):
                print("copying ancillary file", artifact.location)
                shutil.copy(artifact.location, self._workspace)
        visitor = SourceVisitor(copy_acillary_file)
        descender = TreeDescent(source)
        descender.descend(visitor)

        # now do the main fab run
        visitor = SourceVisitor(self._extend_queue)
        descender = TreeDescent(source)
        descender.descend(visitor)

        self._queue.check_queue_done()
        self._queue.shutdown()

        file_db = FileInfoDatabase(self._state)
        for file_info in file_db:
            print(file_info.filename)
            # Where files are generated in the working directory
            # by third party tools, we cannot guarantee the hashes
            if file_info.filename.match(f'{self._workspace}/*'):
                print('    hash: --hidden-- (generated file)')
            else:
                print(f'    hash: {file_info.adler32}')

        fortran_db = FortranWorkingState(self._state)
        for fortran_info in fortran_db:
            print(fortran_info.unit.name)
            print('    found in: ' + str(fortran_info.unit.found_in))
            print('    depends on: ' + str(fortran_info.depends_on))

        c_db = CWorkingState(self._state)
        for c_info in c_db:
            print(c_info.symbol.name)
            print('    found_in: ' + str(c_info.symbol.found_in))
            print('    depends on: ' + str(c_info.depends_on))

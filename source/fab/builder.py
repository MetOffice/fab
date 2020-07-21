##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
import logging
from pathlib import Path

from fab.database import SqliteStateDatabase, FileInfoDatabase
from fab.artifact import \
    Artifact, \
    FortranSource, \
    BinaryObject, \
    Seen, \
    Raw, \
    Analysed, \
    Compiled
from fab.tasks.fortran import \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranAnalyser, \
    FortranCompiler, \
    FortranLinker
from fab.source_tree import \
    TreeDescent, \
    SourceVisitor
from fab.queue import QueueManager
from fab.engine import Engine, PathMap


def entry() -> None:
    """
    Entry point for the Fab build tool.
    """
    import argparse
    import configparser
    import multiprocessing
    import sys
    import fab

    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stderr))

    description = 'Flexible build system for scientific software.'

    config = configparser.ConfigParser(allow_no_value=True)
    config.read('config.ini')
    settings = config['settings']
    flags = config['flags']

    parser = argparse.ArgumentParser(add_help=False,
                                     description=description)
    # We add our own help so as to capture as many permutations of how people
    # might ask for help. The default only looks for a subset.
    parser.add_argument('-h', '-help', '--help', action='help',
                        help='Print this help and exit')
    parser.add_argument('-V', '--version', action='version',
                        version=fab.__version__,
                        help='Print version identifier and exit')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Produce a running commentary on progress')
    parser.add_argument('-w', '--workspace', metavar='PATH', type=Path,
                        default=Path.cwd() / 'working',
                        help='Directory for working files.')
    parser.add_argument('--nprocs', action='store', type=int, default=2,
                        choices=range(2, multiprocessing.cpu_count()),
                        help='Provide number of processors available for use,'
                             'default is 2 if not set.')
    # TODO: Flags will eventually come from configuration
#    parser.add_argument('--fpp-flags', action='store', type=str, default='',
#                        help='Provide flags for Fortran PreProcessor ')
    # TODO: Flags will eventually come from configuration
#    parser.add_argument('--fc-flags', action='store', type=str, default='',
#                        help='Provide flags for Fortran Compiler')
    # TODO: Flags will eventually come from configuration
#    parser.add_argument('--ld-flags', action='store', type=str, default='',
#                        help='Provide flags for Fortran Linker')
    # TODO: Name for executable will eventually come from configuration
#    parser.add_argument('--exec-name', action='store', type=str, default='',
#                        help='Name of executable (default is the name of '
#                             'the target program)')
    # TODO: Target/s will eventually come from configuration
#    parser.add_argument('target', action='store', type=str,
#                        help='The top level unit name to compile')
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build')
    arguments = parser.parse_args()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    # If not provided, name the exec after the target
    if arguments.exec_name == '':
        arguments.exec_name = arguments.target

    application = Fab(arguments.workspace,
                      # arguments.target,
                      # arguments.exec_name,
                      settings['target'],
                      settings['exec-name'],
                      # arguments.fpp_flags,
                      # arguments.fc_flags,
                      # arguments.ld_flags,
                      flags['fpp-flags'],
                      flags['fc-flags'],
                      flags['ld-flags'],
                      arguments.nprocs)
    application.run(arguments.source)


class Fab(object):
    def __init__(self,
                 workspace: Path,
                 target: str,
                 exec_name: str,
                 fpp_flags: str,
                 fc_flags: str,
                 ld_flags: str,
                 n_procs: int):

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
        ]

        # Initialise the required Tasks, providing them with any static
        # properties such as flags to use, workspace location etc
        # TODO: Eventually the tasks may instead access many of these
        # properties via the configuration (at Task runtime, to allow for
        # file-specific overrides?)
        fortran_preprocessor = FortranPreProcessor(
            'cpp', ['-traditional-cpp', '-P'] + fpp_flags.split(), workspace
        )
        fortran_analyser = FortranAnalyser(workspace)
        fortran_compiler = FortranCompiler(
            'gfortran',
            ['-c', '-J', str(workspace)] + fc_flags.split(), workspace
        )
        # TODO: Linker class is probably generic not Fortran specific
        # now that we are passing in the command to use?
        fortran_linker = FortranLinker(
            'gfortran', ld_flags.split(), workspace, exec_name
        )

        # The Task map tells the engine what Task it should be using
        # to deal with Artifacts depending on their type and state
        task_map = {
            (FortranSource, Seen): fortran_preprocessor,
            (FortranSource, Raw): fortran_analyser,
            (FortranSource, Analysed): fortran_compiler,
            (BinaryObject, Compiled): fortran_linker,
        }

        engine = Engine(workspace,
                        target,
                        path_maps,
                        task_map)
        self._queue = QueueManager(n_procs - 1, engine)

    def _extend_queue(self, artifact: Artifact) -> None:
        self._queue.add_to_queue(artifact)

    def run(self, source: Path):

        self._queue.run()

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

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from collections import defaultdict
import logging
from pathlib import Path
from typing import Dict, List, Type

from fab import FabException
from fab.database import SqliteStateDatabase, FileInfoDatabase
from fab.artifact import \
    Artifact, \
    FortranSource, \
    Seen, \
    Raw, \
    Analysed
from fab.tasks import Command
from fab.tasks.common import CommandTask
from fab.tasks.fortran import \
    FortranWorkingState, \
    FortranPreProcessor, \
    FortranAnalyser, \
    FortranUnitID, \
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
    import multiprocessing
    import sys
    import fab

    logger = logging.getLogger('fab')
    logger.addHandler(logging.StreamHandler(sys.stderr))

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
    parser.add_argument('--fpp-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran PreProcessor ')
    # TODO: Flags will eventually come from configuration
    parser.add_argument('--fc-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran Compiler')
    # TODO: Flags will eventually come from configuration
    parser.add_argument('--ld-flags', action='store', type=str, default='',
                        help='Provide flags for Fortran Linker')
    # TODO: Name for executable will eventually come from configuration
    parser.add_argument('--exec-name', action='store', type=str, default='',
                        help='Name of executable (default is the name of '
                             'the target program)')
    # TODO: Target/s will eventually come from configuration
    parser.add_argument('target', action='store', type=str,
                        help='The top level unit name to compile')
    parser.add_argument('source', type=Path,
                        help='The path of the source tree to build')
    arguments = parser.parse_args()

    if arguments.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    application = Fab(arguments.workspace,
                      arguments.target,
                      arguments.exec_name,
                      arguments.fpp_flags,
                      arguments.fc_flags,
                      arguments.ld_flags,
                      arguments.nprocs)
    application.run(arguments.source)


class Fab(object):
    _compile_map = [
        PathMap(r'.*\.f90', FortranSource, Analysed),
    ]

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
        self._target = target
        self._exec_name = exec_name

        self._command_flags_map: Dict[Type[Command], List[str]] = {}
        if fc_flags != '':
            self._command_flags_map[FortranCompiler] = (
                fc_flags.split()
            )
        if ld_flags != '':
            self._command_flags_map[FortranLinker] = (
                ld_flags.split()
            )

        path_maps = [
            PathMap(r'.*\.f90', FortranSource, Raw),
            PathMap(r'.*\.F90', FortranSource, Seen),
        ]

        # TODO: We setup the task instances here to
        # avoid them being repeatedly instantiated
        # later; with all required "static" properties.
        # Eventually quite a few of these will probably
        # come from the configuration instead
        fortran_preprocessor = FortranPreProcessor(
            'cpp', ['-traditional-cpp', '-P'] + fpp_flags.split(), workspace
        )
        fortran_analyser = FortranAnalyser(workspace)

        task_map = {
            (FortranSource, Raw): fortran_analyser,
            (FortranSource, Seen): fortran_preprocessor,
        }

        self._engine = Engine(workspace,
                              target,
                              path_maps,
                              task_map)
        self._queue = QueueManager(n_procs - 1, self._engine)

    def _extend_queue(self, artifact: Artifact) -> None:
        self._queue.add_to_queue(artifact)

    def run(self, source: Path):

        self._queue.run()

        visitor = SourceVisitor(self._extend_queue)
        descender = TreeDescent(source)
        descender.descend(visitor)

        self._queue.check_queue_done()

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

        # TODO: remove this stuff!  Aborting at this point
        # while refactoring
        self._queue.shutdown()
        return

        # Start with the top level program unit
        target_info = fortran_db.get_program_unit(self._target)
        if len(target_info) > 1:
            alt_filenames = [str(info.unit.found_in) for info in target_info]
            message = f"Ambiguous top-level program unit '{self._target}', " \
                      f"found in: {', '.join(alt_filenames)}"
            raise FabException(message)
        unit_to_process: List[FortranUnitID] = [target_info[0].unit]

        # Initialise linker
        if self._exec_name != "":
            executable = Path(self._workspace) / self._exec_name
        else:
            executable = Path(self._workspace / self._target)

        flags = self._command_flags_map.get(FortranLinker, [])
        link_command = FortranLinker(self._workspace, flags, executable)

        processed_units: List[FortranUnitID] = []

        while unit_to_process:
            # Pop pending items from start of the list
            unit = unit_to_process.pop(0)
            if unit in processed_units:
                continue

            dependencies: Dict[str, List[FortranUnitID]] = defaultdict(list)
            for prereq in fortran_db.depends_on(unit):
                dependencies[prereq.name].append(prereq)
            for name, alt_prereqs in dependencies.items():
                if len(alt_prereqs) > 1:
                    filenames = [str(path) for path in alt_prereqs]
                    message = f"Ambiguous prerequiste '{name}' " \
                              f"found in: {', '.join(filenames)}"
                    raise FabException(message)
                unit_to_process.append(alt_prereqs[0])

            # Construct names of any expected module files to
            # pass to the compiler constructor
            # TODO: Note that this currently assumes all of the
            #       dependencies we found were modules; we are
            #       going to need a way to get that information
            #       from the database
            mod_files = [Path(self._workspace /
                              dependee).with_suffix('.mod')
                         for dependee in dependencies.keys()]

            # TODO: It would also be good here to be able to
            #       generate a list of mod files which we
            #       expect to be *produced* by the compile
            #       and pass this to the constructor for
            #       inclusion in the task's "products"
            compiler_class = (
                self._compile_map.get_task(unit.found_in)
            )
            if compiler_class is None:
                continue

            if issubclass(compiler_class, FortranCompiler):
                flags = self._command_flags_map.get(compiler_class, [])
                compiler = CommandTask(
                    compiler_class(
                        unit.found_in,
                        self._workspace,
                        flags,
                        mod_files))
            else:
                message = \
                    f'Unhandled class "{compiler_class}" in compiler map.'
                raise TypeError(message)

            self._queue.add_to_queue(compiler)
            # Indicate that this unit has been processed, so we
            # don't do it again if we encounter it a second time
            processed_units.append(unit)
            # Add the object files to the linker
            # TODO: For right now products is a list, though the
            #       compiler only ever produces a single entry;
            #       maybe add_object should accept Union[Path, List[Path]]?
            link_command.add_object(compiler.products[0])

        # Hopefully by this point the list is exhausted and
        # everything has been compiled, and the linker is primed
        linker = CommandTask(link_command)
        self._queue.add_to_queue(linker)
        self._queue.check_queue_done()
        self._queue.shutdown()

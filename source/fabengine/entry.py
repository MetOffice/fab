from __future__ import annotations

from cProfile import Profile
from logging import StreamHandler, DEBUG, INFO, WARNING
from queue import Empty
from traceback import format_exception
from time import sleep

from multiprocessing import Barrier, Process, get_logger as mp_get_logger
from pathlib import Path
from queue import Queue

from fabengine.actions import Action, ActionResult
from fabengine.actions.configurator import RosePicker
from fabengine.actions.sentinel import Sentinel
from fabengine.project import Project
from fabengine.repository import Repository, FileTreeRepository
from fabengine.database import Database
from fabengine.manager import FabManager
from fabengine.mpdequeue import MPDEQueue


class MonitorProcess(Process):
    def __init__(self, work_queue: MPDEQueue[Action]):
        super().__init__(name="Build monitor", target=self._monitor)
        self._work_queue = work_queue
        self._stopping = False

    def stop(self) -> None:
        self._stopping = True

    def _monitor(self):
        logger = mp_get_logger()
        sleep_count = 0
        while not self._stopping:
            sleep(1)
            sleep_count += 1
            self._stopping |= self._work_queue.stopping()
            if sleep_count < 11:
                continue
            sleep_count = 0

            logger.info("---")
            logger.info(f"Queue stopping: {self._work_queue.stopping()}")
            length = self._work_queue.length()
            for action, tally in self._work_queue.work_tally().items():
                percentage = 100 * tally / length
                logger.info(
                    f"{tally} ({int(percentage)}%): {action.__name__} on queue"
                )

        logger.debug("Monitor stopped")


class WorkerProcess(Process):
    def __init__(self,
                 work_queue: MPDEQueue[Action],
                 result_queue: Queue[ActionResult],
                 database: Database,
                 sentinal_barrier: Barrier,
                 profile: bool):
        self._work_queue = work_queue
        self._result_queue = result_queue
        self._database = database
        self._sentinel_barrier = sentinal_barrier
        self._profile = profile
        super().__init__(name="Build worker", target=self._worker)

    def _worker(self):
        if self._profile:
            profiler = Profile()
            profiler.enable()
        else:
            profiler = None

        logger = mp_get_logger()

        self._work_queue.append(Sentinel())

        while not self._work_queue.stopping():
            # We stop on a barrier at the sentinel to make sure we don't loose
            # any actions down the cracks.
            #
            # Todo: Is there a better way to do this which doesn't involve a
            #       barrier?
            action: Action = self._work_queue.popleft()

            if isinstance(action, Sentinel):
                barrier_id = self._sentinel_barrier.wait()
                self._work_queue.append(action)
                if barrier_id == 0:
                    logger.info("Sentinel comes round: " + str(self.pid))
                    logger.info("Number of actions processed this round: "
                                + str(self._database.processed_last_round))

                if self._database.processed_last_round == 0:
                    logger.debug("Stop requested")
                    self._work_queue.stop()
                continue

            try:
                logger.debug("Trying: " + str(action))
                ready = True
                for prereq in action.prerequisites():
                    this_ready = prereq.ready()
                    logger.debug(f"Testing ({this_ready}): {prereq}")
                    ready &= this_ready
                if not ready:
                    logger.debug("Requeueing: " + str(action))
                    self._work_queue.append(action)
                    continue
            except Exception as ex:
                logger.error("Exception in prerequisites: " + str(ex))
                result = ActionResult(action, cause=ex)
                self._result_queue.put(result)
                self._work_queue.stop()

            try:
                logger.debug("Performing: " + str(action))
                requeued = False
                for thing in action.perform():
                    if isinstance(thing, ActionResult):
                        logger.debug("Queueing result: " + str(thing))
                        self._result_queue.put(thing)
                        if thing.return_code != 0:
                            logger.debug("Action failed, requesting stop")
                            self._work_queue.stop()
                            continue
                    elif isinstance(thing, Action):
                        if thing is action:
                            logger.info("Requeueing action: " + str(thing))
                            self._work_queue.append(thing)  # Always to back
                            requeued = True
                        else:
                            logger.debug("Queueing action: " + str(thing))
                            # Todo: Strategy pattern for enqueueing
                            if self._database.queue_new_on_front:
                                self._work_queue.appendleft(thing)
                            else:
                                self._work_queue.append(thing)
                    else:
                        raise RuntimeError(
                            "Unexpected object on result queue: " + str(thing)
                        )
                if not requeued:
                    self._database.bump_processed_tally()
                logger.debug("Done: " + str(action))
            except Exception as ex:
                logger.error("Exception in process: " + str(ex))
                result = ActionResult(action, cause=ex)
                self._result_queue.put(result)
                self._work_queue.stop()

        logger.debug("Done processing actions")

        if self._profile and profiler is not None:
            profiler.disable()
            profiler.dump_stats(f'profile.{self.pid}.txt')


def main(work_dir: Path, worker_threads:int, no_monitor: bool = False,
         profile: bool = False, log_level: int = WARNING,
         *repositories: Repository):
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / 'build').mkdir(exist_ok=True)

    logger = mp_get_logger()
    logger.setLevel(log_level)
    logger.addHandler(StreamHandler())

    with FabManager() as manager:
        # Todo: Hardwired variables
        database = Database(
            {
                # Physics from the UM
                'UM_PHYSICS': 'true',
                'LFRIC': 'true',
                'USSPREC_32B': 'true',
                'LSPREC_32B': 'true',
                'UM_JULES': 'true',
                # I/O platform
                'USE_XIOS': 'true',
                # Component precision
                'RDEF_PRECISION': '64',
                'R_SOLVER_PRECISION': '32',
                'R_TRAN_PRECISION': '64',
                'R_BL_PRECISION': '64',
                # Transitional
                'LEGACY_MPI': 'true'
            },
            [
                'funit', 'pfunit',  # pFUnit
                'mpi', 'mpi_f08',  # MPI
                'netcdf',  # NetCDF
                'omp_lib',  # OpenMP
                'xios', 'icontext', 'mod_wait', 'mod_oasis',  # XIOS/OASIS
                'yaxt',  # YAXT
                'vernier_mod',  # Vernier
                'c_shum_byteswap'  # ShUMlib
            ],
            [
                'netcdff', 'netcdf',
                'xios',
                'yaxt', 'yaxt_c',
                'pfunit', 'funit', 'fargparse', 'gftl-shared-v2',
                'stdc++'
            ],
            [
                {'real': 'real32'},
                {'real': 'real64'},
                {'integer': 'int32'}
            ],
            {
                'um': ['-fdefault-real-8', '-fdefault-double-8']
            },
            {
                Path('science/physics_schemes/source'): ['um'],
                Path('jules/source'): ['um'],
                Path('socrates/source'): ['um'],
                Path('interfaces/physics_schemes_interface/source/legacy'): ['um']
            },
            manager
        )
        sentinel_barrier = Barrier(worker_threads,
                                   action=database.reset_work_done)

        work_queue = manager.MPDEQueue()
        result_queue = manager.Queue()
        for repository in repositories:
            repo_action = repository.create_action(work_dir, database)
            work_queue.append(repo_action)

            for project in repository.projects:
                if project.configuration_meta_data is None:
                    continue

                meta_data_path = repo_action.working_copy / project.configuration_meta_data
                if project.configuration_meta_data.name == 'rose-meta.conf':
                    # Todo: Don't like Core reference here
                    work_queue.append(
                        RosePicker(meta_data_path,
                                   work_dir / 'build' / 'configuration',
                                   work_dir / 'lfric_core', database)
                    )
                else:  # Is a directory
                    database.config_meta_dirs.append(meta_data_path)

        workers: list[WorkerProcess] = []
        for _ in range(worker_threads):
            process = WorkerProcess(work_queue, result_queue, database,
                                    sentinel_barrier, profile)
            process.start()
            workers.append(process)

        if not no_monitor:
            monitor = MonitorProcess(work_queue)
            monitor.start()

        try:
            for process in workers:
                process.join()
        except KeyboardInterrupt:
            work_queue.stop()
            for process in workers:
                process.join()

        if not no_monitor:
            monitor.stop()
            monitor.join()

        try:
            while True:
                remainder = work_queue.pop()
                logger.warning(
                    f"Still on the queue: {remainder}"
                )
                for prereq in remainder.prerequisites():
                    logger.warning(f"Waiting for ({prereq.ready()}) {prereq}")
        except IndexError:
            pass  # Nothing further to do when queue is empty.

        try:
            while True:
                result = result_queue.get(False)
                if result.return_code == 0 and result.cause is None:  # Success
                    message = "Completed: " + str(result.action)
                    if result.stdout:
                        message += "\n" + result.stdout
                    logger.info(message)
                else:  # Failure
                    message = "Failed " + str(result.action)
                    if result.command:
                        message += "\nCommand: " + result.command
                    if result.stderr:
                        message += "\nError: " + result.stderr
                    if result.cause:
                        message += "\nCause: " \
                        + ''.join(format_exception(result.cause))
                    logger.error(message)
        except Empty:
            pass  # Nothing further to do when queue is empty.


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--debug', '-d', action='store_true')
    parser.add_argument('--threads', '-j', type=int, default=1)
    parser.add_argument('--work-dir', type=Path, default='work')
    parser.add_argument('--no-monitor', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('target',
                        choices=['skeleton', 'atmosphere'], default='skeleton')
    arguments = parser.parse_args()

    level = WARNING
    if arguments.verbose:
        level = INFO
    if arguments.debug:
        level = DEBUG

    if arguments.target == 'skeleton':
        components = [
            Project(Path('infrastructure')),
            Project(Path('components/driver')),
            Project(Path('components/science')),
            Project(Path('components/inventory')),
            Project(Path('components/lfric-xios')),
            Project(
                Path('applications/skeleton'),
                configuration_meta_data=Path('rose-meta/lfric-skeleton/HEAD/rose-meta.conf')
            )
        ]
        main(arguments.work_dir, arguments.threads,
             arguments.no_monitor, arguments.profile,
             level,
             FileTreeRepository(f'localhost:{Path().absolute()}/lfric_core',
                                projects=components)
             )
    elif arguments.target == 'atmosphere':
        main(arguments.work_dir, arguments.threads,
             arguments.no_monitor, arguments.profile,
             level,
             FileTreeRepository(f'localhost:{Path().absolute()}/lfric_core',
                                [
                                    Project(Path('infrastructure')),
                                    Project(Path('components/driver')),
                                    Project(Path('components/science')),
                                    Project(Path('components/inventory')),
                                    Project(Path('components/lfric-xios'))
                                ]),
            FileTreeRepository(
                     f'localhost:{Path().absolute()}/lfric_apps',
                     [
                        Project(Path('interfaces/physics_schemes_interface')),
                        Project(Path('science/shared'), 'bucket'),
                        Project(Path('interfaces/socrates_interface')),
                        Project(Path('interfaces/jules_interface')),
                        Project(Path('science/gungho')),
                        Project(
                            Path('applications/lfric_atm'),
                            configuration_meta_data=Path(
                                'rose-meta/lfric-lfric_atm/HEAD/rose-meta.conf'
                            )
                        )
                    ]
                 ),
                 FileTreeRepository(
                     f'localhost:{Path().absolute()}/extract/extract',
                     [
                         Project(Path('casim'), source_dir=Path('src')),
                         Project(Path('ukca'), source_dir=Path('src'))
                     ]
                 ),
                 FileTreeRepository(
                     f'localhost:{Path().absolute()}/jules_interface/extract',
                     [Project(Path('jules'), source_dir=Path('src'))]
                 ),
                 FileTreeRepository(
                     f'localhost:{Path().absolute()}/socrates_interface/extract',
                     [Project(Path('socrates'), source_dir=Path('src'))]
                 )
        )
    else:
        raise RuntimeError("Unrecognised target: " + arguments.target)

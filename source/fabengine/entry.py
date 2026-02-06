from __future__ import annotations

from cProfile import Profile
from logging import StreamHandler, getLogger, DEBUG, INFO, WARNING
from time import sleep

from multiprocessing import Barrier, Process, Queue, get_logger as mp_get_logger
from pathlib import Path

from fabengine.actions import (Action, ActionException,
                               ExceptionActionException, EndOfWorkException,
                               WorkerException)
from fabengine.actions.configurator import RosePicker
from fabengine.actions.sentinel import Sentinel
from fabengine.project import Project
from fabengine.repository import Repository, FileTreeRepository
from fabengine.database import Configuration, Database
from fabengine.manager import FabManager
from fabengine.work_queue import QueueStrategy, WorkQueue


class MonitorProcess(Process):
    def __init__(self, work_queue: WorkQueue):
        super().__init__(name="Build monitor", target=self._monitor)
        self._work_queue = work_queue
        self._stopping = False

    def stop(self) -> None:
        self._stopping = True

    def _monitor(self):
        logger = getLogger(__name__)
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
            length = self._work_queue.length
            for action, tally in self._work_queue.work_tally().items():
                percentage = 100 * tally / length()
                logger.info(
                    f"{tally} ({int(percentage)}%): {action.__name__} on queue"
                )

        logger.debug("Monitor stopped")


class WorkerProcess(Process):
    def __init__(self,
                 work_queue: WorkQueue,
                 result_queue: Queue[WorkerException],
                 database: Database,
                 sentinel_barrier: Barrier,
                 profile: bool):
        self._work_queue = work_queue
        self._result_queue = result_queue
        self._database = database
        self._sentinel_barrier = sentinel_barrier
        self._profile = profile
        super().__init__(name="Build worker", target=self._worker)

    def _worker(self):
        if self._profile:
            profiler = Profile()
            profiler.enable()
        else:
            profiler = None

        logger = getLogger(__name__)

        self._work_queue.new_action(Sentinel())

        while not self._work_queue.stopping():
            # We stop on a barrier at the sentinel to make sure we don't loose
            # any actions down the cracks.
            #
            # Todo: Is there a better way to do this which doesn't involve a
            #       barrier?
            action: Action = self._work_queue.pop()

            if isinstance(action, Sentinel):
                barrier_id = self._sentinel_barrier.wait()
                self._work_queue.requeue_action(action)
                if barrier_id == 0:
                    self._work_queue.leave_barrier()
                    logger.info("Sentinel comes round: " + str(self.pid))
                    logger.info("Number of actions processed this round: "
                                + str(self._database.processed_last_round))

                if self._database.processed_last_round == 0:
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
                    self._work_queue.requeue_action(action)
                    continue
            except Exception as ex:
                logger.error("Exception in prerequisites: " + str(ex))
                result = ExceptionActionException(action, cause=ex)
                self._result_queue.put(result)
                self._work_queue.stop()

            try:
                logger.debug("Performing: " + str(action))
                try:
                    resulting_actions = action.perform()
                    #
                    # An action is only considered "stalled" if it returns only
                    # itself.
                    #
                    if resulting_actions != [action]:
                        self._database.bump_processed_tally()
                    for resulting_action in resulting_actions:
                        if resulting_action is action:  # Action returned itself
                            self._work_queue.requeue_action(resulting_action)
                        else:
                            self._work_queue.new_action(resulting_action)
                except ActionException as result:
                    logger.debug("Queueing result: " + str(result))
                    self._result_queue.put(result)
                    logger.debug("Action failed, requesting stop")
                    self._work_queue.stop()
                logger.debug("Done: " + str(action))
            except Exception as ex:
                logger.error("Exception in process: " + str(ex))
                result = ExceptionActionException(action, cause=ex)
                self._result_queue.put(result)
                self._work_queue.stop()

        logger.debug("Done processing actions")
        self._result_queue.put(EndOfWorkException())

        if self._profile and profiler is not None:
            profiler.disable()
            profiler.dump_stats(f'profile.{self.pid}.txt')


def main(work_dir: Path, worker_threads:int, no_monitor: bool = False,
         profile: bool = False, log_level: int = WARNING,
         stack_strategy: QueueStrategy = QueueStrategy.ALWAYS_TO_BACK,
         *repositories: Repository):
    logger = getLogger(__name__)
    logger.setLevel(log_level)
    logger.addHandler(StreamHandler())

    mp_logger = mp_get_logger()
    mp_logger.setLevel(WARNING)
    mp_logger.addHandler(StreamHandler())

    configuration = Configuration(
        work_dir,
        work_dir / 'lfric_core' / 'etc' / 'psyclone.cfg',
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
            'casim/': ['um'],
            'jules/': ['um'],
            'physics_schemes/': ['um'],
            'physics_schemes_interface/legacy/': ['um'],
            'socrates/': ['um'],
            'ukca/': ['um']
        }
    )

    with FabManager() as manager:
        work_queue: WorkQueue = manager.WorkQueue(stack_strategy)

        def hit_sentinel() -> None:
            database.reset_work_done()
            work_queue.enter_barrier()

        database = Database(configuration, manager)
        sentinel_barrier = Barrier(worker_threads, action=hit_sentinel)

        result_queue = manager.Queue()
        for repository in repositories:
            repo_action = repository.create_action(work_dir, database)
            work_queue.new_action(repo_action)

            for project in repository.projects:
                if project.configuration_meta_data is None:
                    continue

                meta_data_path = repo_action.local_copy / project.configuration_meta_data
                if project.configuration_meta_data.name == 'rose-meta.conf':
                    # Todo: Don't like Core reference here
                    work_queue.new_action(
                        RosePicker(meta_data_path, work_dir / 'lfric_core',
                                   database)
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

        results: list[ActionException] = []
        workers_stopped = 0
        while workers_stopped < worker_threads:
            try:
                result = result_queue.get()
                if isinstance(result, EndOfWorkException):
                    workers_stopped += 1
                else:
                    results.append(result)
            except KeyboardInterrupt:
                work_queue.stop()

        remainder: list[Action] = []
        try:
            while True:
                remainder.append(work_queue.pop())
        except IndexError:
            pass  # No more to do

        for process in workers:
            process.join()

        if not no_monitor:
            monitor.stop()
            monitor.join()

        for action in remainder:
            message = "Still on the queue: " + str(action)
            for prereq in action.prerequisites():
                message += f"\nWaiting for ({prereq.ready()}) {prereq}"
            logger.warning(message)

        for result in results:
            logger.error("Failed " + result.describe())


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--debug', '-d', action='store_true')
    parser.add_argument('--threads', '-j', type=int, default=1)
    parser.add_argument('--work-dir', type=Path, default='work')
    parser.add_argument('--no-monitor', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--queue-strategy',
                        choices=[strat.name.lower() for strat in QueueStrategy],
                        default='always_to_back')
    parser.add_argument('target',
                        choices=['skeleton', 'atmosphere'], default='skeleton')
    arguments = parser.parse_args()

    level = WARNING
    if arguments.verbose:
        level = INFO
    if arguments.debug:
        level = DEBUG

    if arguments.target == 'skeleton':
        repositories = [
            FileTreeRepository(
                f'localhost:{Path().absolute()}/lfric_core',
                [
                    Project(Path('infrastructure')),
                    Project(Path('components/driver')),
                    Project(Path('components/science')),
                    Project(Path('components/inventory')),
                    Project(Path('components/lfric-xios')),
                    Project(
                        Path('applications/skeleton'),
                        configuration_meta_data=Path(
                            'rose-meta/lfric-skeleton/HEAD/rose-meta.conf'
                        )
                    )
                ]
            )
        ]

    elif arguments.target == 'atmosphere':
        repositories = [
            FileTreeRepository(
                'lfric_core',
                [
                    Project(Path('infrastructure')),
                    Project(Path('components/driver')),
                    Project(Path('components/science')),
                    Project(Path('components/inventory')),
                    Project(Path('components/lfric-xios'))
                ]
            ),
            FileTreeRepository(
                'lfric_apps',
                [
                    Project(Path('interfaces/physics_schemes_interface')),
                    Project(Path('science/physics_schemes')),
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
                'casim.filtered',
                [
                    Project(Path('.'), identifier='casim',
                            source_dir=Path('src'))
                ]
            ),
            FileTreeRepository(
                'ukca.filtered',
                [
                    Project(Path('.'), identifier='ukca',
                            source_dir=Path('src'))
                ]
            ),
            FileTreeRepository(
                'jules.filtered',
                [
                    Project(Path('.'), identifier='jules',
                            source_dir=Path('src'))
                ]
            ),
            FileTreeRepository(
                'socrates.filtered',
                [
                    Project(Path('.'), identifier='socrates',
                            source_dir=Path('src'))
                ]
            )
        ]

    else:
        raise RuntimeError("Unrecognised target: " + arguments.target)

    main(arguments.work_dir, arguments.threads,
         arguments.no_monitor, arguments.profile,
         level, QueueStrategy[arguments.queue_strategy.upper()],
         *repositories
         )

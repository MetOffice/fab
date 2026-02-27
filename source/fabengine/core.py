from __future__ import annotations

from logging import StreamHandler, getLogger, WARNING
from multiprocessing import get_logger as mp_get_logger, Barrier
from pathlib import Path
from queue import Queue

from fabengine.actions import Action, EndOfWorkException, WorkerException
from fabengine.actions.configurator import RosePicker
from fabengine.configuration import FabConfiguration
from fabengine.database import Configuration, Database
from fabengine.manager import FabManager
from fabengine.processes import WorkerProcess, MonitorProcess
from fabengine.work_queue import QueueStrategy


def fab_core(
    fab_configuration: FabConfiguration,
    work_dir: Path,
    worker_threads: int,
    monitor: bool = True,
    profile: bool = False,
    stack_strategy: QueueStrategy = QueueStrategy.ALWAYS_TO_BACK,
):
    """
    Build system entry point.

    :param fab_configuration: Describes the build.
    :param work_dir: Directory used as scratch space for build.
    :param worker_threads: Number of workers to use.
    :param monitor: Run progress monitor.
    :param profile: Enable profiling of run.
    :param stack_strategy: Use this when adding actions to queue.
    """
    mp_logger = mp_get_logger()
    mp_logger.setLevel(WARNING)
    mp_logger.addHandler(StreamHandler())

    configuration = Configuration(
        work_dir,
        psyclone_config = work_dir / "lfric_core" / "etc" / "psyclone.cfg",
        fpp_definitions = {
            # Physics from the UM
            "UM_PHYSICS": "true",
            "LFRIC": "true",
            "USSPREC_32B": "true",
            "LSPREC_32B": "true",
            "UM_JULES": "true",
            # I/O platform
            "USE_XIOS": "true",
            # Component precision
            "RDEF_PRECISION": "64",
            "R_SOLVER_PRECISION": "32",
            "R_TRAN_PRECISION": "64",
            "R_BL_PRECISION": "64",
            # Transitional
            "LEGACY_MPI": "true",
        },
        fc_ignore_modules = [
            "funit",
            "pfunit",  # pFUnit
            "mpi",
            "mpi_f08",  # MPI
            "netcdf",  # NetCDF
            "omp_lib",  # OpenMP
            "xios",
            "icontext",
            "mod_wait",
            "mod_oasis",  # XIOS/OASIS
            "yaxt",  # YAXT
            "vernier_mod",  # Vernier
            "c_shum_byteswap",  # ShUMlib
        ],
        libraries = [
            "netcdff",
            "netcdf",
            "xios",
            "yaxt",
            "yaxt_c",
            "pfunit",
            "funit",
            "fargparse",
            "gftl-shared-v2",
            "stdc++",
        ],
        field_instances = [
            {"real": "real32"},
            {"real": "real64"},
            {"integer": "int32"}
        ],
        build_tags = {"um": ["-fdefault-real-8", "-fdefault-double-8"]},
        tag_dirs = {
            "casim/": ["um"],
            "jules/": ["um"],
            "physics_schemes/": ["um"],
            "physics_schemes_interface/legacy/": ["um"],
            "socrates/": ["um"],
            "ukca/": ["um"],
        },
        inclusion_suffixes = [".h", ".inc"],
    )

    with FabManager() as manager:
        work_queue = manager.WorkQueue(stack_strategy)  # type:ignore

        def hit_sentinel() -> None:
            database.reset_work_done()
            work_queue.enter_barrier()

        database = Database(configuration, manager)
        sentinel_barrier = Barrier(worker_threads, action=hit_sentinel)

        result_queue: Queue[WorkerException] = manager.Queue()
        for repository in fab_configuration.repositories():
            repo_action = repository.create_action(work_dir, database)
            work_queue.new_action(repo_action)

            for project in repository.projects:
                if project.configuration_meta_data is None:
                    continue

                meta_data_path = (
                    repo_action.local_copy / project.configuration_meta_data
                )
                if project.configuration_meta_data.name == "rose-meta.conf":
                    # Todo: Don't like Core reference here
                    work_queue.new_action(
                        RosePicker(meta_data_path, work_dir / "lfric_core", database)
                    )
                else:  # Is a directory
                    database.config_meta_dirs.append(meta_data_path)

        workers: list[WorkerProcess] = []
        for _ in range(worker_threads):
            process = WorkerProcess(
                work_queue, result_queue, database, sentinel_barrier, profile
            )
            process.start()
            workers.append(process)

        if monitor:
            monitor_process = MonitorProcess(work_queue)
            monitor_process.start()

        results: list[WorkerException] = []
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

        if monitor:
            monitor_process.stop()
            monitor_process.join()

        for action in remainder:
            message = "Still on the queue: " + str(action)
            for prereq in action.prerequisites():
                message += f"\nWaiting for ({prereq.ready()}) {prereq}"
            getLogger(__name__).warning(message)

        for result in results:
            getLogger(__name__).error("Failed " + result.describe())

from __future__ import annotations

from logging import StreamHandler, getLogger, WARNING
from multiprocessing import get_logger as mp_get_logger, Barrier
from pathlib import Path
from queue import Queue
from typing import Optional

from fabengine.actions import Action, EndOfWorkException, WorkerException
from fabengine.actions.configurator import RosePicker
from fabengine.build_script import BuildScript
from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import Configuration, Database, Performance
from fabengine.manager import FabManager
from fabengine.package import Package, partition_specification, pkg_config, LibraryName
from fabengine.processes import WorkerProcess, MonitorProcess
from fabengine.work_queue import QueueStrategy


# Todo, convert core to a class with methods called from entry.
# Todo, store command line options more neatly (here), and pass into database
#       to be added to the new write once configuration.
def fab_core(
    build_script: BuildScript,
    package_table: dict[str, Package],
    work_dir: Path,
    worker_threads: int,
    monitor: bool = True,
    stack_strategy: QueueStrategy = QueueStrategy.ALWAYS_TO_BACK,
    timing_file: Optional[Path] = None,
):
    """
    Build system entry point.

    :param build_script: Describes the build.
    :param package_table: Map of library name to details.
    :param work_dir: Directory used as scratch space for build.
    :param worker_threads: Number of workers to use.
    :param monitor: Run progress monitor.
    :param stack_strategy: Use this when adding actions to queue.
    :param timing_file: File to receive action timings.
    """
    mp_logger = mp_get_logger()
    mp_logger.setLevel(WARNING)
    mp_logger.addHandler(StreamHandler())

    packages: list[Package] = []
    for specification in build_script.libraries():
        package_name, _, _ = partition_specification(specification)
        if package_name in package_table:
            packages.append(package_table[package_name])
        else:  # package_name not in package_table
            packages.append(pkg_config(specification))

    # Todo: Hardwired C++ runtime. Need a proper solution for language runtimes.
    #
    packages.append(Package("stdc++", (), [], [LibraryName("stdc++")]))

    # Todo: Port configuration to write once configuration for all actions
    configuration = Configuration(
        fpp_definitions={
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
        fc_ignore_modules=[
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
        field_instances=[{"real": "real32"}, {"real": "real64"}, {"integer": "int32"}],
        build_tags={"um": ["-fdefault-real-8", "-fdefault-double-8"]},
        tag_dirs={
            "casim/": ["um"],
            "jules/": ["um"],
            "physics_schemes/": ["um"],
            "physics_schemes_interface/legacy/": ["um"],
            "socrates/": ["um"],
            "ukca/": ["um"],
        },
        inclusion_suffixes=[".h", ".inc"],
        packages=tuple(packages),
        performance_file=timing_file,
    )

    with FabManager() as manager:
        work_queue = manager.WorkQueue(stack_strategy)  # type:ignore

        def hit_sentinel() -> None:
            database.reset_work_done()
            work_queue.enter_barrier()

        # Insatiate the build config from the fab file and add the work dir
        build_script_config = build_script.configuration()
        if 'paths' not in build_script_config:
            build_script_config['paths'] = WriteOnceDict({})
        build_script_config['paths']['work_dir'] = work_dir
        build_script_config['paths']['work_dir'].mkdir(exist_ok=True)
        build_script_config['paths']['build_dir'] = build_script_config['paths']['work_dir'] / "build"
        build_script_config['paths']['build_dir'].mkdir(exist_ok=True)
        build_script_config['paths']['module_dir'] = build_script_config['paths']['build_dir'] / "modules"
        build_script_config['paths']['module_dir'].mkdir(exist_ok=True)

        # Initialise the database with the build script config and the manager
        database = Database(build_script_config, configuration, manager)

        sentinel_barrier = Barrier(worker_threads, action=hit_sentinel)

        performance = Performance(manager)
        result_queue: Queue[WorkerException] = manager.Queue()
        for repository in build_script.repositories():
            repo_action = repository.create_action(work_dir, database)

            for identifier, path in repository.paths.items():
                full_path = repo_action.local_copy() / path
                database.config["paths"][identifier] = full_path

            for project in repository.projects:
                for identifier, path in project.paths.items():
                    full_path = repo_action.local_copy() / project.project_dir / path
                    database.config["paths"][identifier] = full_path

                if project.configuration_meta_data is None:
                    continue

                meta_data_path = (
                    repo_action.local_copy() / project.configuration_meta_data
                )
                if project.configuration_meta_data.name == "rose-meta.conf":
                    # Todo: Don't like Core reference here
                    work_queue.new_action(RosePicker(meta_data_path, database))
                else:  # Is a directory
                    database.config_meta_dirs.append(meta_data_path)

            work_queue.new_action(repo_action)

        workers: list[WorkerProcess] = []
        for _ in range(worker_threads):
            process = WorkerProcess(
                work_queue, result_queue, database, sentinel_barrier, performance
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

        if configuration.performance_file:
            with configuration.performance_file.open("wt") as fhandle:
                tally = performance.aggregate_action_log()
                for action_str in sorted(tally.keys()):
                    print(action_str + ", " + str(tally[action_str]), file=fhandle)

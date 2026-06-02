from __future__ import annotations

from logging import StreamHandler, getLogger, WARNING
from multiprocessing import get_logger as mp_get_logger, Barrier
from queue import Queue

from fabengine.actions import Action, EndOfWorkException, WorkerException
from fabengine.actions.configurator import RosePicker
from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import Database, Performance
from fabengine.manager import FabManager
from fabengine.processes import WorkerProcess, MonitorProcess


# Todo, convert core to a class with methods called from entry.
def fab_core(
    script_config: WriteOnceDict,
    build_config: WriteOnceDict,
):
    """
    Build system entry point.

    :param script_config: Configuration settings for the build script
    :param build_config: Configuration settings for the build
    """
    mp_logger = mp_get_logger()
    mp_logger.setLevel(WARNING)
    mp_logger.addHandler(StreamHandler())

    with FabManager() as manager:
        work_queue = manager.WorkQueue(script_config["queue_strategy"])  # type:ignore

        def hit_sentinel() -> None:
            database.reset_work_done()
            work_queue.enter_barrier()

        # Initialise the database with the build script config and the manager
        database = Database(script_config, build_config, manager)

        sentinel_barrier = Barrier(script_config["worker_threads"], action=hit_sentinel)

        performance = Performance(manager)
        result_queue: Queue[WorkerException] = manager.Queue()
        for repository in build_config["repositories"]:
            repo_action = repository.create_action(
                script_config["paths"]["work_dir"], database
            )

            for identifier, path in repository.paths.items():
                full_path = repo_action.local_copy() / path
                database.script_config["paths"][identifier] = full_path

            for project in repository.projects:
                for identifier, path in project.paths.items():
                    full_path = repo_action.local_copy() / project.project_dir / path
                    database.script_config["paths"][identifier] = full_path

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
        for _ in range(script_config["worker_threads"]):
            process = WorkerProcess(
                work_queue, result_queue, database, sentinel_barrier, performance
            )
            process.start()
            workers.append(process)

        if script_config["monitor"]:
            monitor_process = MonitorProcess(work_queue)
            monitor_process.start()

        results: list[WorkerException] = []
        workers_stopped = 0
        while workers_stopped < script_config["worker_threads"]:
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

        if script_config["monitor"]:
            monitor_process.stop()
            monitor_process.join()

        for action in remainder:
            message = "Still on the queue: " + str(action)
            for prereq in action.prerequisites():
                message += f"\nWaiting for ({prereq.ready()}) {prereq}"
            getLogger(__name__).warning(message)

        for result in results:
            getLogger(__name__).error("Failed " + result.describe())

        if script_config["paths"]["performance_file"]:
            with script_config["paths"]["performance_file"].open("wt") as fhandle:
                tally = performance.aggregate_action_log()
                for action_str in sorted(tally.keys()):
                    print(action_str + ", " + str(tally[action_str]), file=fhandle)

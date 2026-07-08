from __future__ import annotations

from logging import StreamHandler, getLogger, DEBUG, INFO
from multiprocessing import get_logger as mp_get_logger, Barrier
from queue import Queue

from fabengine.actions import Action, EndOfWorkException, WorkerException
from fabengine.actions.configurator import RosePicker
from fabengine.configuration_tools import WriteOnceDict
from fabengine.database import Database, Performance
from fabengine.manager import FabManager
from fabengine.processes import WorkerProcess, MonitorProcess


# Todo, convert core to a class with methods called from entry.
def fab_core(configuration: WriteOnceDict):
    """
    Build system entry point.
    """
    mp_logger = mp_get_logger()
    mp_logger.addHandler(StreamHandler())
    if getLogger(__name__).getEffectiveLevel() == DEBUG:
        # If we put the multiprocess logger into "debug" level we get an
        # incredible amount of chatter from the multiprocess library itself.
        # This is only useful if there is a fundamental problem.
        #
        mp_logger.setLevel(INFO)
    else:
        mp_logger.setLevel(getLogger(__name__).level)

    with FabManager() as manager:
        database = Database(configuration, manager)

        work_queue = manager.WorkQueue(configuration["queue_strategy"])  # type:ignore

        def hit_sentinel() -> None:
            database.reset_work_done()
            work_queue.enter_barrier()

        sentinel_barrier = Barrier(configuration["worker_threads"], action=hit_sentinel)

        performance = Performance(manager)
        result_queue: Queue[WorkerException] = manager.Queue()
        for repository in configuration["repositories"]:
            repo_action = repository.create_action(database)

            for identifier, path in repository.paths.items():
                full_path = repo_action.local_copy() / path
                database.configuration["paths"][identifier] = full_path

            for project in repository.projects:
                for identifier, path in project.paths.items():
                    full_path = repo_action.local_copy() / project.project_dir / path
                    database.configuration["paths"][identifier] = full_path

                if project.configuration_meta_data is None:
                    continue

                meta_data_path = (
                    repo_action.local_copy() / project.configuration_meta_data
                )
                if project.configuration_meta_data.name == "rose-meta.conf":
                    work_queue.new_action(RosePicker(meta_data_path, database))
                else:  # Is a directory
                    database.config_meta_dirs.append(meta_data_path)

            work_queue.new_action(repo_action)

        workers: list[WorkerProcess] = []
        for _ in range(configuration["worker_threads"]):
            process = WorkerProcess(
                work_queue, result_queue, database, sentinel_barrier, performance
            )
            process.start()
            workers.append(process)

        if configuration["monitor"]:
            monitor_process = MonitorProcess(work_queue)
            monitor_process.start()

        results: list[WorkerException] = []
        workers_stopped = 0
        while workers_stopped < configuration["worker_threads"]:
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

        if configuration["monitor"]:
            monitor_process.stop()
            monitor_process.join()

        for action in remainder:
            message = "Still on the queue: " + str(action)
            for prereq in action.prerequisites():
                message += f"\nWaiting for ({prereq.ready()}) {prereq}"
            getLogger(__name__).warning(message)

        for result in results:
            getLogger(__name__).error("Failed " + result.describe())

        if configuration["paths"]["performance_file"]:
            with configuration["paths"]["performance_file"].open("wt") as stream:
                tally = performance.aggregate_action_log()
                for action_str in sorted(tally.keys()):
                    print(f'"{action_str}", {tally[action_str]}', file=stream)

        database.artefact_store.dump_map()

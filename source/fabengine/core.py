from __future__ import annotations

from logging import DEBUG, INFO, StreamHandler, getLogger
from multiprocessing import Barrier
from multiprocessing import get_logger as mp_get_logger
from queue import Queue

from rich.console import Console  # type: ignore

from fabengine.actions import Action, EndOfWorkException, WorkerException
from fabengine.actions.configurator import RosePicker
from fabengine.actions.sentinel import Sentinel
from fabengine.configuration_tools import WriteOnceDict
from fabengine.cui import format_file_details, show_errors, show_stalled_actions
from fabengine.database import Database, Performance, PrerequisiteInfo, PrerequisiteType
from fabengine.manager import FabManager
from fabengine.processes import MonitorProcess, SignalHandler, WorkerProcess


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

        for symbol, prereqs in configuration["forced_prerequisites"].items():
            database.prerequisites[symbol] = [
                PrerequisiteInfo(prereq, PrerequisiteType.FORCED) for prereq in prereqs
            ]

        sentinel_barrier = Barrier(configuration["worker_threads"], action=hit_sentinel)

        database.configuration["force_include_dir"] = []
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

                for path in project.force_include_dir:
                    full_path = repo_action.local_copy() / project.source_dir / path
                    database.configuration["force_include_dir"].append(full_path)

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

        signaller = SignalHandler()

        results: list[WorkerException] = []
        workers_stopped = 0
        while (
            workers_stopped < configuration["worker_threads"] and not signaller.stopping
        ):
            try:
                result = result_queue.get()
                if isinstance(result, EndOfWorkException):
                    workers_stopped += 1
                else:
                    results.append(result)
            except KeyboardInterrupt:
                work_queue.stop()

        if signaller.stopping:
            mp_logger.error("controlled shutdown triggered")

        signaller.restore_signals()

        remainder: list[Action] = []
        try:
            while not signaller.stopping:
                action = work_queue.pop()
                if isinstance(action, Sentinel):
                    continue
                remainder.append(action)
        except IndexError:
            pass  # No more to do

        for process in workers:
            process.join()

        if configuration["monitor"]:
            monitor_process.stop()
            monitor_process.join()

        if signaller.stopping:
            # Do not produce diagnostics if build has been interrupted
            raise SystemExit(1)
        console = Console()

        # todo: systematise the exit codes
        show_errors(console, results)
        if results:
            raise SystemExit(2)

        show_stalled_actions(console, remainder)
        if remainder:
            raise SystemExit(2)

        if configuration["paths"]["performance_file"]:
            with configuration["paths"]["performance_file"].open("wt") as stream:
                tally = performance.aggregate_action_log()
                for action_str in sorted(tally.keys()):
                    print(f'"{action_str}", {tally[action_str]}', file=stream)

        database.artefact_store.dump_map()

        # todo: fix the proxy
        for artefact in database.artefact_store._getvalue():
            if artefact.get_meta("binary_target") is not None:
                print(format_file_details(artefact.real_filename))

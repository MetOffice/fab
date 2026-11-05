from __future__ import annotations

from multiprocessing import Process
from queue import Queue
from signal import SIG_DFL, SIGABRT, SIGINT, SIGTERM, signal
from threading import BrokenBarrierError
from time import sleep

from fabengine.actions import (
    Action,
    ActionException,
    EndOfWorkException,
    ExceptionActionException,
    WorkerException,
)
from fabengine.cui.status import set_ps_name
from fabengine.database import Database
from fabengine.logserver import make_logger, make_loggers
from fabengine.metrics import PerformanceTable, PerformanceTimer
from fabengine.work_queue import Sentinel, WorkQueue


class SignalHandler:
    """Class to catch and handle signals in Processes."""

    def __init__(self):
        self._stopping = False
        self._setup_signals()

    @property
    def stopping(self):
        return self._stopping

    def _stop_process(self, signum, frame):
        """Begin a controlled shutdown of the Process."""
        self._stopping = True

    def _setup_signals(self):
        """Set signals which trigger a controlled shutdown."""
        for sig in (SIGABRT, SIGINT, SIGTERM):
            signal(sig, self._stop_process)

    def restore_signals(self):
        """Restore the default behaviours."""
        for sig in (SIGABRT, SIGINT, SIGTERM):
            signal(sig, SIG_DFL)


class MonitorProcess(Process, SignalHandler):
    """
    Reports on build progress.
    """

    def __init__(self, work_queue: WorkQueue):
        """
        :param work_queue: Queue to monitor.
        """
        super().__init__(name="Build monitor", target=self._monitor)
        SignalHandler.__init__(self)
        self._work_queue = work_queue

    def stop(self) -> None:
        """
        Signals process to stop.
        """
        self._stopping = True

    @set_ps_name
    def _monitor(self):
        """
        Body of subprocess.
        """
        logger = make_logger("user")
        sleep_count = 0
        while not self._stopping:
            sleep(1)
            sleep_count += 1
            self._stopping |= self._work_queue.stopping()
            if sleep_count < 11:
                continue
            sleep_count = 0

            logger.info(f"Queue stopping: {self._work_queue.stopping()}")
            length = self._work_queue.length
            for action, tally in self._work_queue.work_tally().items():
                percentage = 100 * tally / length()
                name = action.__name__ if hasattr(action, "__name__") else action
                logger.info(f"{tally} ({int(percentage)}%): {name} on queue")

        logger.debug("Monitor stopped")


class WorkerProcess(Process, SignalHandler):
    """
    Task farmworker process.
    """

    def __init__(
        self,
        work_queue: WorkQueue,
        result_queue: Queue[WorkerException],
        database: Database,
        sentinel_barrier,
        performance: PerformanceTable,
    ):
        """
        :param work_queue: Queue to pull work from and push it to.
        :param result_queue: Queue to push results to.
        :param database: Build system state and configuration.
        :param sentinel_barrier: Synchronisation object.
        :param performance: Timing collection object.
        """
        self._work_queue = work_queue
        self._result_queue = result_queue
        self._database = database
        self._sentinel_barrier = sentinel_barrier
        self._performance = performance
        self._user_logger, self._system_logger = make_loggers()
        super().__init__(target=self._worker)
        SignalHandler.__init__(self)

    @set_ps_name
    def _worker(self) -> None:
        """
        Body of the subprocess.
        """
        self._work_queue.new_action(Sentinel())

        while not self._work_queue.stopping() and not self._stopping:
            # We stop on a barrier at the sentinel to make sure we don't loose
            # any actions down the cracks.
            #
            # Todo: Is there a better way to do this which doesn't involve a
            #       barrier?
            with PerformanceTimer("__queue"):
                action: Action = self._work_queue.pop()

            if isinstance(action, Sentinel):
                try:
                    with PerformanceTimer("__barrier"):
                        barrier_id = self._sentinel_barrier.wait()
                    if barrier_id == 0:
                        self._work_queue.leave_barrier()
                        self._system_logger.info(
                            "Sentinel comes round: " + str(self.pid)
                        )
                        self._system_logger.info(
                            "Number of actions processed this round: "
                            + str(self._database.processed_last_round)
                        )
                    if self._database.processed_last_round == 0:
                        self._work_queue.stop()
                except BrokenBarrierError:
                    self._work_queue.stop()  # Ensure we're stopping

                self._work_queue.requeue_action(action)
                continue

            try:
                self._system_logger.debug("Trying: " + str(action))
                ready = True
                for prereq in action.prerequisites():
                    this_ready = prereq.ready()
                    self._system_logger.debug(f"Testing ({this_ready}): {prereq}")
                    ready &= this_ready
                if not ready:
                    self._work_queue.requeue_action(action)
                    continue
            except Exception as ex:  # noqa: BLE001
                self._system_logger.error(
                    f"Exception in prerequisites: ({prereq}) {ex}"
                )
                result = ExceptionActionException(action, ex)
                self._result_queue.put(result)
                self._work_queue.stop()

            try:
                self._user_logger.debug("Performing: " + str(action))
                try:
                    with PerformanceTimer(action.__class__.__name__) as timer:
                        resulting_actions = action.perform()
                        timer.set_reuse(action.reused)
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
                    self._system_logger.debug("Queueing result: " + str(result))
                    self._result_queue.put(result)
                    self._system_logger.debug("Action failed, requesting stop")
                    self._work_queue.stop()
                self._user_logger.debug("Done: " + str(action))
            except Exception as ex:  # noqa: BLE001
                self._system_logger.error("Exception in process: " + str(ex))
                self._result_queue.put(ExceptionActionException(action, ex))
                self._work_queue.stop()

        # Add timings to the global performance table
        for key, values in PerformanceTimer.items():
            for measurement in values:
                self._performance.add(self.name, key, measurement)

        # Release any workers waiting on a sentinel
        #
        self._sentinel_barrier.reset()

        self._user_logger.debug("Done processing actions")
        self._result_queue.put(EndOfWorkException())

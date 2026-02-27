from __future__ import annotations

from cProfile import Profile
from logging import getLogger
from multiprocessing import Process
from queue import Queue
from threading import BrokenBarrierError
from time import sleep

from fabengine.actions import (
    Action,
    ActionException,
    EndOfWorkException,
    ExceptionActionException,
    WorkerException,
)
from fabengine.database import Database
from fabengine.work_queue import Sentinel, WorkQueue


class MonitorProcess(Process):
    """
    Reports on build progress.
    """

    def __init__(self, work_queue: WorkQueue):
        """
        :param work_queue: Queue to monitor.
        """
        super().__init__(name="Build monitor", target=self._monitor)
        self._work_queue = work_queue
        self._stopping = False

    def stop(self) -> None:
        """
        Signals process to stop.
        """
        self._stopping = True

    def _monitor(self):
        """
        Body of subprocess.
        """
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
                logger.info(f"{tally} ({int(percentage)}%): {action.__name__} on queue")

        logger.debug("Monitor stopped")


class WorkerProcess(Process):
    """
    Task farm worker process.
    """

    def __init__(
        self,
        work_queue: WorkQueue,
        result_queue: Queue[WorkerException],
        database: Database,
        sentinel_barrier,
        profile: bool,
    ):
        """
        :param work_queue: Queue to pull work from and push it to.
        :param result_queue: Queue to push results to.
        :param database: Build system state and configuration.
        :param sentinel_barrier: Synchronisation object.
        :param profile: Turn profiling on and off.
        """
        self._work_queue = work_queue
        self._result_queue = result_queue
        self._database = database
        self._sentinel_barrier = sentinel_barrier
        self._profile = profile
        super().__init__(name="Build worker", target=self._worker)

    def _worker(self) -> None:
        """
        Body of the subprocess.
        """
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
                try:
                    barrier_id = self._sentinel_barrier.wait()
                    if barrier_id == 0:
                        self._work_queue.leave_barrier()
                        logger.info("Sentinel comes round: " + str(self.pid))
                        logger.info(
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
                logger.error("Exception in prerequisites: ({prereq}) {ex}")
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
                self._result_queue.put(ExceptionActionException(action, ex))
                self._work_queue.stop()

        # Release any workers waiting on a sentinel
        #
        self._sentinel_barrier.reset()

        logger.debug("Done processing actions")
        self._result_queue.put(EndOfWorkException())

        if self._profile and profiler is not None:
            profiler.disable()
            profiler.dump_stats(f"profile.{self.pid}.txt")

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''
import logging
from queue import Empty as QueueEmpty
from typing import List, Dict
from multiprocessing import \
    Queue, \
    JoinableQueue, \
    Process, \
    Lock, \
    Manager, \
    Event
from multiprocessing.synchronize import Lock as LockT
from multiprocessing.synchronize import Event as EventT

from fab.artifact import Artifact
from fab.engine import Engine, DiscoveryState


def _worker(queue: JoinableQueue,
            engine: Engine,
            discovery: Dict[str, DiscoveryState],
            objects: List[Artifact],
            lock: LockT,
            stopswitch: EventT):
    while not stopswitch.is_set():
        try:
            artifact = queue.get(block=True, timeout=0.5)
        except QueueEmpty:
            continue

        try:
            new_artifacts = engine.process(artifact,
                                           discovery,
                                           objects,
                                           lock)

            for new_artifact in new_artifacts:
                queue.put(new_artifact)
        finally:
            queue.task_done()


class QueueManager(object):
    def __init__(self, n_workers: int, engine: Engine):
        self._queue: Queue = JoinableQueue()
        self._n_workers = n_workers
        self._workers: List[int] = []
        self._engine = engine
        self._mgr = Manager()
        self._discovery: Dict[str, DiscoveryState] = self._mgr.dict({})
        self._stopswitch: EventT = Event()
        self._objects: List[Artifact] = self._mgr.list([])
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)

    def add_to_queue(self, artifact: Artifact):
        self._queue.put(artifact)

    def run(self):
        for _ in range(self._n_workers):
            process = Process(
                target=_worker, args=(self._queue,
                                      self._engine,
                                      self._discovery,
                                      self._objects,
                                      self._lock,
                                      self._stopswitch))
            process.start()
            self._workers.append(process)

    def check_queue_done(self):
        # Blocks until the JoinableQueue is empty
        self._queue.join()

    def shutdown(self):
        # Set the stop switch and wait for workers
        # to finish
        self._stopswitch.set()
        for process in self._workers:
            process.join(10.0)

        # Any that didn't finish nicely at this point
        # can be forcibly stopped
        for i_worker, process in enumerate(self._workers):
            if process.is_alive():
                msg = f"Terminating thread {i_worker}..."
                self.logger.warn(msg)
                process.terminate()

        # Stop the queue
        self._queue.close()
        self._queue.join_thread()
        self._workers.clear()

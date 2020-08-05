##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''
from queue import Empty as QueueEmpty
from typing import List, Mapping
from multiprocessing import \
    Queue, \
    JoinableQueue, \
    Process, \
    Lock, \
    Manager, \
    Event
from fab.artifact import Artifact
from fab.engine import Engine


def _worker(queue: JoinableQueue,
            engine: Engine,
            discovery,
            objects,
            lock,
            stopswitch):
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
        self._discovery: Mapping[str, str] = self._mgr.dict({})
        self._stopswitch = Event()
        self._objects: List = self._mgr.list([])
        self._lock = Lock()

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
        for process in self._workers:
            if process.is_alive():
                process.terminate()

        # Stop the queue
        self._queue.close()
        self._queue.join_thread()
        self._workers.clear()

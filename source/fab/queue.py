##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''
from typing import List
from multiprocessing import \
    Queue, \
    JoinableQueue, \
    Process, \
    Lock, \
    Manager
from fab.artifact import Artifact
from fab.engine import Engine


class Stop(Artifact):
    def __init__(self):
        pass


def _worker(queue: JoinableQueue,
            engine: Engine,
            discovery,
            objects,
            lock):
    while True:
        artifact = queue.get(block=True)
        if isinstance(artifact, Stop):
            break

        new_artifacts = engine.process(artifact,
                                       discovery,
                                       objects,
                                       lock)

        for new_artifact in new_artifacts:
            queue.put(new_artifact)

        queue.task_done()

    queue.task_done()


class QueueManager(object):
    def __init__(self, n_workers: int, engine: Engine):
        self._queue: Queue = JoinableQueue()
        self._n_workers = n_workers
        self._workers: List[int] = []
        self._engine = engine
        self._mgr = Manager()
        self._discovery = self._mgr.dict({engine.target: "HeardOf"})
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
                                      self._lock))
            process.start()
            self._workers.append(process)

    def check_queue_done(self):
        # Blocks until the JoinableQueue is empty
        self._queue.join()

    def shutdown(self):
        stop = Stop()
        for _ in range(self._n_workers):
            self._queue.put(stop)
        self.check_queue_done()
        self._workers.clear()

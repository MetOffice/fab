##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''
from typing import List
from multiprocessing import Queue, JoinableQueue, Process
from fab.tasks import Task


class StopTask(Task):
    def run(self):
        return []

    @property
    def prerequisites(self):
        return []

    @property
    def products(self):
        return []


def worker(queue: JoinableQueue):
    while True:
        task = queue.get(block=True)
        if isinstance(task, StopTask):
            break
        if all([prereq.exists() for prereq in task.prerequisites]):
            task.run()
        else:
            queue.put(task)
        queue.task_done()
    queue.task_done()


class QueueManager(object):
    def __init__(self, n_workers: int):
        self._queue: Queue = JoinableQueue()
        self._n_workers = n_workers
        self._workers: List[int] = []

    def add_to_queue(self, task: Task):
        self._queue.put(task)

    def run(self):
        for _ in range(self._n_workers):
            process = Process(
                target=worker, args=(self._queue,))
            process.start()
            self._workers.append(process)

    def check_queue_done(self):
        # Blocks until the JoinableQueue is empty
        self._queue.join()

    def shutdown(self):
        stop = StopTask()
        for _ in range(self._n_workers):
            self._queue.put(stop)
        self.check_queue_done()
        self._workers.clear()

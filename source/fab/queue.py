##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''

from multiprocessing import Queue, JoinableQueue, Process
from fab.language import Task


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
        # TODO: Check here whether the task *can*
        #       be run - if prerequisites are not
        #       present then you
        #       cannot run and should call
        #       queue.put(task)
        task.run()
        queue.task_done()


class QueueManager(object):
    def __init__(self, n_workers: int):
        self._queue: Queue = JoinableQueue()
        self._n_workers = n_workers

    def add_to_queue(self, task: Task):
        self._queue.put(task)

    def run(self):
        for _ in range(self._n_workers):
            process = Process(
                target=worker, args=(self._queue,))
            process.start()

    def check_queue_done(self):
        # Blocks until the JoinableQueue is empty
        self._queue.join()

    def shutdown(self):
        stop = StopTask()
        for _ in range(self._n_workers):
            self._queue.put(stop)

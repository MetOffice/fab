##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Classes and methods relating to the queue system
'''

from multiprocessing import Queue, Process
from typing import List
from pathlib import Path
from fab.language import Task


class StopTask(Task):
    def run(self):
        return []


def worker(queue: Queue, rendezvous: List[Path]):
    while True:
        task = queue.get(block=True)
        if isinstance(task, StopTask):
            break
        # TODO: Check here whether the task *can*
        #       be run - if prerequisites are not
        #       present (in rendezvous) then you
        #       cannot run and should call
        #       queue.put(task)
        rendezvous.extend(task.run())


class QueueManager(object):
    def __init__(self, n_workers: int):
        self._queue: Queue = Queue()
        self._n_workers = n_workers
        self._rendezvous: List[Path] = []

    def add_to_queue(self, task: Task):
        self._queue.put(task)

    def get_queue_length(self):
        length = self._queue.qsize()
        return length

    def run(self):
        for _ in range(self._n_workers):
            process = Process(
                target=worker, args=(self._queue,
                                     self._rendezvous))
            process.start()

    def shutdown(self):
        stop = StopTask()
        for _ in range(self._n_workers):
            self._queue.put(stop)

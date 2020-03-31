##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.queue import QueueManager
from fab.language import Task


class DummyTask(Task):
    def __init__(self, taskno):
        self._taskno = taskno

    def run(self):
        print("Running task", self._taskno, "...")
        print("Finished task.")
        return [self._taskno]


def test_queue():

    q_manager = QueueManager(1)

    for i in range(1, 11):
        task = DummyTask(i)
        q_manager.add_to_queue(task)

    print("The queue length is ", q_manager.get_queue_length())
    q_manager.run()

    q_manager.shutdown()

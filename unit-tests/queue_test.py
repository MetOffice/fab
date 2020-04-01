##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.queue import QueueManager
from fab.language import Task
from pathlib import Path
import os


class DummyTask(Task):
    def __init__(self, filename):
        self._filename = filename

    def run(self):
        os.system("touch " + str(self._filename))

    @property
    def prerequisites(self):
        return []

    @property
    def products(self):
        return []


def test_queue(tmp_path: Path):

    q_manager = QueueManager(2)
    q_manager.run()

    for i in range(1, 4):
        filename = tmp_path / f"file_{i}"
        task = DummyTask(filename)
        q_manager.add_to_queue(task)

    q_manager.check_queue_done()
    q_manager.shutdown()

    for i in range(1, 4):
        filename = tmp_path / f"file_{i}"
        assert filename.exists()


def test_startstop():
    q_manager = QueueManager(1)
    q_manager.run()
    q_manager.shutdown()

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
    def __init__(self, filename, depends_on=[]):
        self._filename = filename
        self._depends_on = depends_on

    def run(self):
        os.system("touch " + str(self._filename))

    @property
    def prerequisites(self):
        return self._depends_on

    @property
    def products(self):
        return [self._filename]


def test_queue(tmp_path: Path):

    q_manager = QueueManager(2)
    q_manager.run()

    for i in range(1, 4):
        filename = tmp_path / f"file_{i}"
        task = DummyTask(filename)
        q_manager.add_to_queue(task)

    q_manager.check_queue_done()

    for i in range(1, 4):
        filename = tmp_path / f"file_{i}"
        assert filename.exists()

    q_manager.shutdown()


def test_check_prerequisites(tmp_path: Path):

    q_manager = QueueManager(1)
    q_manager.run()

    dependant_file = tmp_path / "dependant"
    prereq_file = tmp_path / "prereq"

    dependant_task = DummyTask(dependant_file, depends_on=[prereq_file])
    q_manager.add_to_queue(dependant_task)

    prereq_task = DummyTask(prereq_file)
    q_manager.add_to_queue(prereq_task)

    q_manager.check_queue_done()

    assert prereq_file.exists()
    assert dependant_file.exists()

    q_manager.shutdown()


def test_startstop():
    q_manager = QueueManager(1)
    q_manager.run()
    assert len(q_manager._workers) == 1
    q_manager.shutdown()
    assert len(q_manager._workers) == 0

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from fab.queue import QueueManager
from fab.artifact import Artifact, Unknown, New
from fab.engine import Engine
from pathlib import Path
import subprocess
from typing import List


class DummyEngine(Engine):
    def __init__(self):
        self._target = "target"

    def process(self,
                artifact: Artifact,
                shared,
                objects,
                lock) -> List[Artifact]:
        subprocess.run(['touch', str(artifact.location)], check=True)
        return []


def test_queue(tmp_path: Path):

    dummy_engine = DummyEngine()

    q_manager = QueueManager(2, dummy_engine)
    q_manager.run()

    for i in range(1, 4):
        artifact = Artifact(tmp_path / f"file_{i}",
                            Unknown,
                            New)
        q_manager.add_to_queue(artifact)

    q_manager.check_queue_done()

    for i in range(1, 4):
        filename = tmp_path / f"file_{i}"
        assert filename.exists()

    q_manager.shutdown()


def test_startstop():
    dummy_engine = DummyEngine()
    q_manager = QueueManager(1, dummy_engine)
    q_manager.run()
    assert len(q_manager._workers) == 1
    q_manager.shutdown()
    assert len(q_manager._workers) == 0

from __future__ import annotations

from multiprocessing.managers import SyncManager

from fabengine.artefact_store import ArtefactStore
from fabengine.metrics import PerformanceTable
from fabengine.work_queue import WorkQueue


class FabManager(SyncManager):
    """
    Multiprocessing shared data manager which understands Fab data.
    """


FabManager.register(ArtefactStore.__name__, ArtefactStore)
FabManager.register(PerformanceTable.__name__, PerformanceTable)
FabManager.register(WorkQueue.__name__, WorkQueue)

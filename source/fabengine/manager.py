from __future__ import annotations

from collections import deque
from multiprocessing.managers import SyncManager

from fabengine.artefact_store import ArtefactStore
from fabengine.metrics import PerformanceTable


class FabManager(SyncManager):
    """
    Multiprocessing shared data manager which understands Fab data.
    """


FabManager.register(ArtefactStore.__name__, ArtefactStore)
FabManager.register("SharedDeque", deque)
FabManager.register(PerformanceTable.__name__, PerformanceTable)

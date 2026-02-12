from __future__ import annotations

from multiprocessing.managers import SyncManager

from fabengine.work_queue import WorkQueue


class FabManager(SyncManager):
    """
    Multiprocessing shared data manager which understands Fab data.
    """

    pass


FabManager.register("WorkQueue", WorkQueue)

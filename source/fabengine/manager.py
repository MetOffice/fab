from __future__ import annotations

from multiprocessing.managers import SyncManager

from fabengine.work_queue import WorkQueue


class FabManager(SyncManager):
    pass


FabManager.register("WorkQueue", WorkQueue)

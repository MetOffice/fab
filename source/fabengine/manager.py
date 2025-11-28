from __future__ import annotations

from multiprocessing.managers import SyncManager

from fabengine.mpdequeue import MPDEQueue

class FabManager(SyncManager):
    pass

FabManager.register('MPDEQueue', MPDEQueue)

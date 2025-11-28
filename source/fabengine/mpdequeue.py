from collections import deque
from typing import Type

from fabengine.actions import Action
from fabengine.actions.sentinel import Sentinel


class MPDEQueue(deque[Action]):
    def __init__(self) -> None:
        super().__init__()
        self._work_tally: dict[Type[Action], int] = {}
        self._length = 0
        self._stop = False

    def stop(self):
        self._stop = True

    def stopping(self) -> bool:
        return self._stop

    def work_tally(self) -> dict[Type[Action], int]:
        return self._work_tally

    def length(self) -> int:
        return self._length

    def dump_queue(self) -> None:
        for action in self:
            print(action)
        print()

    def appendleft(self, item: Action) -> None:
        super().appendleft(item)
        if isinstance(item, Sentinel):
            return
        self._length += 1
        if item.__class__ not in self._work_tally:
            self._work_tally[item.__class__] = 0
        self._work_tally[item.__class__] += 1

    def append(self, item: Action) -> None:
        super().append(item)
        if isinstance(item, Sentinel):
            return
        self._length += 1
        if item.__class__ not in self._work_tally:
            self._work_tally[item.__class__] = 0
        self._work_tally[item.__class__] += 1

    def pop(self, index: int = -1) -> Action:
        item = super().pop()
        if isinstance(item, Sentinel):
            return item
        self._length -= 1
        self._work_tally[item.__class__] -= 1
        if self._work_tally[item.__class__] == 0:
            del(self._work_tally[item.__class__])
        return item

    def popleft(self) -> Action:
        item = super().popleft()
        if isinstance(item, Sentinel):
            return item
        self._length -= 1
        self._work_tally[item.__class__] -= 1
        if self._work_tally[item.__class__] == 0:
            del(self._work_tally[item.__class__])
        return item

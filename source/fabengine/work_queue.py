from collections import defaultdict, deque
from enum import Enum, auto
from logging import getLogger

from fabengine.actions import Action
from fabengine.actions.sentinel import Sentinel


# Todo: Can this be managed by the strategy pattern?
#
class QueueStrategy(Enum):
    ALWAYS_TO_BACK = auto()
    NEW_TO_FRONT = auto()
    SENTINEL_MAGIC = auto()
    SENTINEL_EXTRA_MAGIC = auto()

    def __str__(self) -> str:
        return self.name.lower()


class WorkQueue:
    """
    Manages a queue of work actions.
    """

    def __init__(self, strategy: QueueStrategy = QueueStrategy.ALWAYS_TO_BACK) -> None:
        self._strategy = strategy
        getLogger(__name__).debug("Queue strategy is: " + self._strategy.name.lower())

        self._queue: deque[Action] = deque()
        self._stop = False
        self._in_barrier = False
        self._sentinel: int | None = None
        self._length = 0
        self._work_tally: dict[type[Action], int] = defaultdict(int)

    def stop(self) -> None:
        """
        Signals queue to stop work.
        """
        getLogger(__name__).debug("Stop requested")
        self._stop = True

    # This method cannot be a "property" as it will be accessed through a
    # multiprocessing AutoProxy. These only support methods.
    #
    def stopping(self) -> bool:
        """
        :return: Is queue stopping?
        """
        return self._stop

    def enter_barrier(self):
        """
        Informs queue sentinel barrier is being entered.
        """
        self._in_barrier = True

    def leave_barrier(self):
        """
        Informs queue sentinel barrier is being left.
        """
        self._in_barrier = False

    # This method cannot be a "property" as it will be accessed through a
    # multiprocessing AutoProxy. These only support methods.
    #
    def length(self) -> int:
        """
        Gets number of actions on queue.
        """
        return self._length

    # This method cannot be a "property" as it will be accessed through a
    # multiprocessing AutoProxy. These only support methods.
    #
    def work_tally(self) -> dict[type[Action], int]:
        """
        Gets number of each action type on queue.
        """
        return self._work_tally

    def new_action(self, action: Action) -> None:
        """
        Adds an action to the queue.

        Respects queue strategy.
        """
        getLogger(__name__).debug("Queueing action: " + str(action))
        if isinstance(action, Sentinel):
            self._add_back(action)
            return

        if self._strategy == QueueStrategy.ALWAYS_TO_BACK:
            self._add_back(action)
        elif self._strategy == QueueStrategy.NEW_TO_FRONT:
            self._add_front(action)
        elif self._strategy == QueueStrategy.SENTINEL_MAGIC:
            if self._in_barrier:
                self._add_back(action)
            else:
                self._add_front(action)
        elif self._strategy == QueueStrategy.SENTINEL_EXTRA_MAGIC:
            if self._in_barrier:
                self._add_after_sentinel(action)
            else:  # Not in barrier
                self._add_front(action)
        else:
            raise RuntimeError("Unrecognised stack strategy: " + self._strategy.name)

    def requeue_action(self, action: Action) -> None:
        """
        Returns action to queue.

        Respects queue strategy.
        """
        getLogger(__name__).debug("Requeueing: " + str(action))
        #
        # Todo: Is there performance to be had by rotating the queue rather
        #       that explicit pop/push?
        #
        self._add_back(action)

    def _add_front(self, item: Action) -> None:
        self._queue.append(item)
        if isinstance(item, Sentinel):
            self._sentinel = len(self._queue) - 1
            return
        if self._sentinel is not None:
            self._sentinel += 1
        self._length += 1
        self._work_tally[item.__class__] += 1

    def _add_back(self, item: Action) -> None:
        self._queue.appendleft(item)
        if isinstance(item, Sentinel):
            self._sentinel = 0
            return
        self._length += 1
        self._work_tally[item.__class__] += 1

    def _add_after_sentinel(self, item: Action) -> None:
        assert not isinstance(item, Sentinel)
        assert self._sentinel is not None
        sentinel = self._queue[self._sentinel]
        assert isinstance(sentinel, Sentinel)

        self._queue.insert(self._sentinel, item)
        self._sentinel += 1
        self._length += 1
        self._work_tally[item.__class__] += 1

    def pop(self) -> Action:
        """
        Gets next work action from queue.
        """
        item = self._queue.pop()
        if isinstance(item, Sentinel):
            self._sentinel = None
            return item
        self._length -= 1
        self._work_tally[item.__class__] -= 1
        if self._work_tally[item.__class__] == 0:
            del self._work_tally[item.__class__]
        return item

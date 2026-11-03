from enum import Enum, auto
from multiprocessing.managers import DictProxy

from fabengine.actions import Action
from fabengine.actions.sentinel import Sentinel
from fabengine.logserver import make_loggers


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

    def __init__(
        self,
        manager,
        tracking: bool = True,
    ) -> None:
        self._tracking = tracking

        self._user_logger, self._system_logger = make_loggers()
        self._system_logger.debug("Queue strategy is: always_to_back")

        # Local data structures
        self._local_actions: dict[int, Action] = {}

        # Shared data structures
        self._queue = manager.SharedDeque()  # type:ignore
        self._shared_actions: DictProxy[int, Action] = manager.dict()  # type:ignore
        self._work_tally: DictProxy[str, int] = manager.dict()  # type:ignore

        # Shared variables
        self._stop = manager.Value("?", False)
        self._in_barrier = manager.Value("?", False)
        self._sentinel = manager.Value("l", -1)
        self._length = manager.Value("L", 0)

        # Lock for non-atomic variable updates
        self._lock = manager.Lock()

    def stop(self) -> None:
        """
        Signals queue to stop work.
        """
        self._user_logger.debug("Stop requested")
        self._stop.value = True

    # This method cannot be a "property" as it will be accessed through a
    # multiprocessing AutoProxy. These only support methods.
    #
    def stopping(self) -> bool:
        """
        :return: Is queue stopping?
        """
        return self._stop.value

    def enter_barrier(self):
        """
        Informs queue sentinel barrier is being entered.
        """
        self._in_barrier.value = True

    def leave_barrier(self):
        """
        Informs queue sentinel barrier is being left.
        """
        self._in_barrier.value = False

    # This method cannot be a "property" as it will be accessed through a
    # multiprocessing AutoProxy. These only support methods.
    #
    def length(self) -> int:
        """
        Gets number of actions on queue.
        """
        return self._length.value

    def work_tally(self):
        """
        Gets number of each action type on queue.
        """
        return self._work_tally

    def new_action(self, action: Action) -> None:
        """
        Adds an action to the back of the queue.
        """
        self._system_logger.debug("Queueing action: " + str(action))
        index = hash(action)

        # todo: this allows the same action to be added more than once.
        # Is this correct?
        if index not in self._shared_actions:
            # Store shared and local copies of the action
            self._shared_actions[index] = action
            self._local_actions[index] = action
        elif not action.__class__ is Sentinel:
            raise ValueError(f"Action clash: {action} ({hash(action)})")

        self._add_back(index, action.__class__.__name__, action.__class__ is Sentinel)

    def requeue_action(self, action: Action) -> None:
        """
        Returns action to queue.

        Respects queue strategy.
        """
        index = hash(action)
        if index not in self._local_actions:
            # We can only re-add something we know about
            raise ValueError("cannot requeue an unknown action")

        self._system_logger.debug("Requeueing: " + str(action))

        # Add the action back on the queue using its index
        self._add_back(index, action.__class__.__name__, action.__class__ is Sentinel)

    def _add_back(self, index: int, name: str, is_sentinel: bool) -> None:
        self._queue.appendleft(index)
        if is_sentinel:
            self._sentinel.value = 0
            return

        with self._lock:
            self._length.value += 1

        if self._tracking:
            # todo: is there a race condition here?
            if name in self._work_tally:
                with self._lock:
                    self._work_tally[name] += 1
            else:
                self._work_tally[name] = 1

    def pop(self) -> Action:
        """
        Gets next work action from queue.
        """
        index = self._queue.pop()
        item = self._get_action(index)

        if item.__class__ is Sentinel:
            self._sentinel.value = -1
            return item

        with self._lock:
            self._length.value -= 1

        if self._tracking:
            # todo: is there a race condition here?
            name = item.__class__.__name__
            if name in self._work_tally:
                with self._lock:
                    self._work_tally[name] -= 1
                    if self._work_tally[name] == 0:
                        del self._work_tally[name]

        return item

    def _get_action(self, index: int) -> Action:
        if index not in self._local_actions:
            # Cache a copy of the global action
            self._local_actions[index] = self._shared_actions[index]
        return self._local_actions[index]

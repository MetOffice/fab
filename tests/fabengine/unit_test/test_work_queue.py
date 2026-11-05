from collections.abc import Iterable
from logging import DEBUG

from fabengine.actions import Action, Prerequisite
from fabengine.actions.sentinel import Sentinel
from fabengine.manager import FabManager
from fabengine.work_queue import WorkQueue
from pytest import raises


class _StubAction(Action):
    def __init__(self, number: int):
        super().__init__(f"stub {number}")
        self.number = number

    def __hash__(self):
        return super().__hash__()

    def __eq__(self, other: object):
        assert isinstance(other, _StubAction)
        return other.number == self.number

    def __str__(self) -> str:
        return "Action " + str(self.number)

    def perform(self) -> Iterable[Action]:
        return []

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []


class TestWorkQueue:
    def test_constructor(self, caplog) -> None:
        caplog.set_level(DEBUG)

        with FabManager() as manager:
            test_unit = WorkQueue(manager)
            assert caplog.records[0].message == "Queue strategy is: always_to_back"
            assert test_unit.stopping() is False
            assert test_unit.length() == 0
            assert test_unit.work_tally()._getvalue() == {}

    def test_new_action(self):
        with FabManager() as manager:
            test_unit = WorkQueue(manager)

            test_unit.new_action(_StubAction(1))
            assert test_unit.length() == 1

            test_unit.new_action(_StubAction(2))
            assert test_unit.length() == 2

            assert test_unit.pop() == _StubAction(1)
            assert test_unit.length() == 1

            test_unit.new_action(_StubAction(3))
            assert test_unit.length() == 2

    def test_action_to_back(self) -> None:
        with FabManager() as manager:
            test_unit = WorkQueue(manager)

            test_unit.new_action(_StubAction(1))
            # Queue: 1
            test_unit.new_action(_StubAction(2))
            # Queue: 1, 2
            test_unit.new_action(_StubAction(3))
            # Queue: 1, 2, 3
            assert test_unit.pop() == _StubAction(1)
            # Queue: 2, 3
            action = test_unit.pop()
            assert action == _StubAction(2)
            test_unit.requeue_action(action)
            # Queue: 3, 2
            sentinel = Sentinel()
            test_unit.new_action(sentinel)
            # Queue: 3, 2, S
            test_unit.new_action(_StubAction(4))
            # Queue: 3, 2, S, 4
            assert test_unit.pop() == _StubAction(3)
            # Queue: 2, S, 4
            action = test_unit.pop()
            assert action == _StubAction(2)
            test_unit.requeue_action(action)
            # Queue: S, 4, 2
            assert test_unit.pop() == sentinel
            test_unit.enter_barrier()
            test_unit.requeue_action(sentinel)
            # Queue: 4, 2, S
            test_unit.new_action(_StubAction(5))
            test_unit.leave_barrier()
            # Queue: 4, 2, S, 5
            assert test_unit.pop() == _StubAction(4)
            # Queue: 2, S, 5
            assert test_unit.pop() == _StubAction(2)
            # Queue: S, 5
            assert test_unit.pop() == sentinel
            test_unit.requeue_action(sentinel)
            # Queue: 5, S
            assert test_unit.pop() == _StubAction(5)
            # Queue: S
            assert test_unit.pop() == sentinel
            # Queue:
            assert test_unit.length() == 0

    def test_requeue(self):

        with FabManager() as manager:
            test_unit = WorkQueue(manager)

            test_unit.new_action(_StubAction(1))
            assert test_unit.pop() == _StubAction(1)
            assert test_unit.length() == 0

            test_unit.requeue_action(_StubAction(1))
            assert test_unit.length() == 1

            with raises(ValueError) as err:
                test_unit.requeue_action(_StubAction(2))
            assert "cannot requeue an unknown action" in str(err.value)

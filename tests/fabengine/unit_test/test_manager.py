from collections import deque

from fabengine.manager import FabManager
from pytest import mark


@mark.parametrize(
    "stype, args, expected",
    [
        ("SharedDeque", [], deque),
    ],
    ids=["SharedDeque"],
)
def test_registration(stype, args, expected):
    with FabManager() as test_unit:
        proxy = getattr(test_unit, stype)(*args)
        # Todo: Obviously using private methods here is bad.
        assert type(proxy._getvalue()) is expected

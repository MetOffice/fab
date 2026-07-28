from __future__ import annotations

from collections.abc import Iterable

from fabengine.actions import Action, Prerequisite


class Sentinel(Action):
    """
    Marks a point in the work queue.
    """

    def __init__(self):
        super().__init__("sentinel")

    def __str__(self) -> str:
        return "Sentinel"

    def prerequisites(self) -> Iterable[Prerequisite]:
        """
        :return: Depends on nothing.
        """
        return []

    def perform(self) -> list[Sentinel]:
        """
        :return: Itself.
        """
        return [self]

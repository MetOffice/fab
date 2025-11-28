from __future__ import annotations

from typing import Iterable

from fabengine.actions import Action, Prerequisite


class Sentinel(Action):
    def __init__(self):
        super().__init__()

    def __str__(self) -> str:
        return "Sentinel"

    def prerequisites(self) -> Iterable[Prerequisite]:
        return []

    def perform(self) -> list[Sentinel]:
        return [self]

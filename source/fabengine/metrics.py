from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path
from time import time
from typing import ClassVar


class PerformanceValue:
    @classmethod
    def get(cls):
        """Create a new instance using current values from times()"""
        return cls(*os.times(), True)

    def __init__(
        self,
        utime: float = 0.0,
        stime: float = 0.0,
        cutime: float = 0.0,
        cstime: float = 0.0,
        elapsed: float = 0.0,
        _get: bool = False,
    ):
        self._timestamp = time()
        self._utime = utime
        self._stime = stime
        self._cutime = cutime
        self._cstime = cstime
        # Replace the times() elapsed with something more accurate
        self._elapsed = self._timestamp if _get else elapsed
        self._reused = False

    def __iadd__(self, other: PerformanceValue):
        self._timestamp = min(self._timestamp, other._timestamp)
        self._utime += other._utime
        self._stime += other._stime
        self._cutime += other._cutime
        self._cstime += other._cstime
        self._elapsed += other._elapsed
        self._reused = self._reused and other._reused
        return self

    def __add__(self, other: PerformanceValue):
        result = PerformanceValue(
            self._utime + other._utime,
            self._stime + other._stime,
            self._cutime + other._cutime,
            self._cstime + other._cstime,
            self._elapsed + other._elapsed,
        )
        result._timestamp = min(self._timestamp, other._timestamp)
        result._reused = self._reused and other._reused
        return result

    def __sub__(self, other: PerformanceValue) -> PerformanceValue:
        result = PerformanceValue(
            self._utime - other._utime,
            self._stime - other._stime,
            self._cutime - other._cutime,
            self._cstime - other._cstime,
            self._elapsed - other._elapsed,
        )
        result._timestamp = min(self._timestamp, other._timestamp)
        result._reused = self._reused or other._reused
        return result

    def __str__(self) -> str:
        return f"{self.elapsed:.2f} (CPU: {self.total_cpu:.2f})"

    def set_reuse(self, flag: bool) -> None:
        self._reused = flag

    @property
    def timestamp(self) -> float:
        return self._timestamp

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def process_cpu(self) -> float:
        return self._utime + self._stime

    @property
    def child_cpu(self) -> float:
        return self._cutime + self._cstime

    @property
    def total_cpu(self) -> float:
        return self.process_cpu + self.child_cpu

    @property
    def reused(self) -> bool:
        return self._reused


class PerformanceTimer:
    _results: ClassVar[dict[str, list[PerformanceValue]]] = {}

    @classmethod
    def reset(cls) -> None:
        """Clear the accumulated results."""
        cls._results = {}

    @classmethod
    def length(cls) -> int:
        return len(cls._results)

    @classmethod
    def items(cls) -> Generator[tuple[str, list[PerformanceValue]], None, None]:
        yield from cls._results.items()

    @classmethod
    def get(cls, name: str, default=None) -> list[PerformanceValue]:
        return cls._results.get(name, default)

    def __init__(self, name: str):
        self._name = name
        self._start = None

    def __enter__(self):
        self._start = PerformanceValue.get()
        return self

    def __exit__(self, *args, **kwargs):
        # todo: ignore cases where an exception has occurred?
        if self._start is None:
            return
        if self._name not in self._results:
            self._results[self._name] = []
        self._results[self._name].append(PerformanceValue.get() - self._start)
        self._start = None

    def set_reuse(self, flag: bool) -> None:
        """Set the reuse flag on the last event."""
        if self._start is None:
            raise RuntimeError("Invalid state")
        self._start.set_reuse(flag)


class PerformanceTable:
    """Centralised performance data."""

    def __init__(self):
        self._global_total = PerformanceValue()
        self._process_total = defaultdict(PerformanceValue)
        self._name_total = defaultdict(PerformanceValue)
        self._all_values = []

    def add(self, process: str, name: str, value: PerformanceValue) -> None:
        """Update the shared tables."""
        self._global_total += value
        self._process_total[process] += value
        self._name_total[name] += value
        self._all_values.append((process, name, value))

    def to_csv(self, filename: Path) -> None:
        """Dump the metrics to a comma separated value file."""

        with filename.open("wt", encoding="utf-8") as fd:
            print("Timestamp,Process,Task,CPU,Elapsed,Reused", file=fd)
            for entry in self._all_values:
                print(
                    f"{entry[2].timestamp},{entry[0]},{entry[1]},{entry[2].total_cpu},"
                    f"{entry[2].elapsed},{entry[2].reused}",
                    file=fd,
                )

    @property
    def process_cpu(self) -> float:
        return self._global_total._utime + self._global_total._stime

    @property
    def child_cpu(self) -> float:
        return self._global_total._cutime + self._global_total._cstime

    @property
    def total_cpu(self) -> float:
        return self._global_total.process_cpu + self._global_total.child_cpu

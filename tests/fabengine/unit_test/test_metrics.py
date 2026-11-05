from pathlib import Path
from time import sleep

from fabengine.metrics import PerformanceTable, PerformanceTimer, PerformanceValue
from pytest import approx, mark


class TestPerformanceValue:
    @mark.parametrize(
        "args,elapsed,process,child,total",
        [
            ([], 0.0, 0.0, 0.0, 0.0),
            ([1, 2], 0.0, 3, 0.0, 3.0),
            ([1, 2, 3, 4, 5], 5, 3, 7, 10),
        ],
        ids=["no values", "some values", "all values"],
    )
    def test_create(self, args, elapsed, process, child, total):
        test_unit = PerformanceValue(*args)
        assert test_unit.elapsed == elapsed
        assert test_unit.process_cpu == process
        assert test_unit.child_cpu == child
        assert test_unit.total_cpu == total
        assert test_unit.reused is False

    def test_get(self):
        test_unit = PerformanceValue.get()
        assert test_unit.elapsed > 0.0

    def test_iadd(self):
        test_unit = PerformanceValue(1, 2, 3, 4, 5)
        test_unit += PerformanceValue(10, 20, 30, 40, 50)

        assert test_unit.elapsed == 55
        assert test_unit.process_cpu == 33
        assert test_unit.child_cpu == 77
        assert test_unit.total_cpu == 110

    def test_add(self):
        test_unit = PerformanceValue(1, 2, 3, 4, 5) + PerformanceValue(
            10, 20, 30, 40, 50
        )

        assert test_unit.elapsed == 55
        assert test_unit.process_cpu == 33
        assert test_unit.child_cpu == 77
        assert test_unit.total_cpu == 110

    def test_sub(self):
        test_unit = PerformanceValue(10, 20, 30, 40, 50) - PerformanceValue(
            1, 2, 3, 4, 5
        )

        assert test_unit.elapsed == 45
        assert test_unit.process_cpu == 27
        assert test_unit.child_cpu == 63
        assert test_unit.total_cpu == 90


class TestPerformanceTimer:
    def test_create(self):
        PerformanceTimer.reset()
        test_unit = PerformanceTimer("alpha")
        assert test_unit._name == "alpha"
        assert PerformanceTimer.length() == 0

    def test_timer(self):
        PerformanceTimer.reset()

        with PerformanceTimer("alpha"):
            for i in range(3):
                with PerformanceTimer("beta"):
                    sleep(0.1)

        assert PerformanceTimer.length() == 2
        assert len(PerformanceTimer.get("alpha")) == 1
        assert len(PerformanceTimer.get("beta")) == 3
        assert PerformanceTimer.get("alpha")[0].elapsed == approx(0.3, rel=0.1)
        assert PerformanceTimer.get("beta")[0].elapsed == approx(0.1, rel=0.1)


class TestPerformanceTable:
    def test_create(self):
        test_unit = PerformanceTable()
        assert isinstance(test_unit._global_total, PerformanceValue)
        assert test_unit.total_cpu == 0.0

    def test_addition(self):
        test_unit = PerformanceTable()

        test_unit.add("p0", "CompileFortran", PerformanceValue(1, 2, 3, 4, 5))
        test_unit.add("p1", "CompileFortran", PerformanceValue(1, 2, 3, 4, 5))

        assert test_unit.process_cpu == 6
        assert test_unit.child_cpu == 14
        assert test_unit.total_cpu == 20
        assert test_unit._process_total["p0"].process_cpu == 3
        assert test_unit._process_total["p0"].child_cpu == 7
        assert test_unit._name_total["CompileFortran"].process_cpu == 6
        assert test_unit._name_total["CompileFortran"].child_cpu == 14
        assert len(test_unit._all_values) == 2

    def test_dump(self, tmp_path: Path):
        filename = tmp_path / "output.csv"

        test_unit = PerformanceTable()
        test_unit.add("p0", "CompileFortran", PerformanceValue(1, 2, 3, 4, 5))
        test_unit.add("p1", "PreprocessFortran", PerformanceValue(1, 2, 3, 4, 5))

        test_unit.to_csv(filename)
        assert filename.exists() is True

        lines = filename.read_text().split("\n")
        assert lines[0].startswith("Timestamp,Process,Task")
        assert "p0,CompileFortran,10,5" in lines[1]
        assert "p1,PreprocessFortran,10,5" in lines[2]

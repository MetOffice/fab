from collections.abc import Iterable
from pathlib import Path

from fabengine.actions import (
    Action,
    Prerequisite,
    SubprocessAction,
    SubprocessActionException,
    TwoPartPath,
)
from pytest import mark, raises
from pytest_subprocess import FakeProcess


class TestTwoPartPath:
    def test_constructor(self):
        test_unit = TwoPartPath(Path("/var/tmp"), Path("wibble"))
        assert test_unit.root == Path("/var/tmp")
        assert test_unit.branch == Path("wibble")
        assert test_unit.full == Path("/var/tmp/wibble")

    def test_constructor_bad_root(self):
        with raises(AssertionError):
            _ = TwoPartPath(Path("work"), Path("bibble"))

    def test_constructor_bad_branch(self):
        with raises(AssertionError):
            _ = TwoPartPath(Path("/var/tmp"), Path("/tmp/wibble"))


class TestAction:
    class ActionHarness(Action):
        def prerequisites(self) -> Iterable[Prerequisite]:
            return []

        def perform(self) -> Iterable[Action]:
            return []

    def test_constructor(self):
        test_unit = TestAction.ActionHarness("fish")
        assert test_unit.action_id == "fish"


class TestSubprocessAction:
    class SubprocessActionHarness(SubprocessAction):
        def prerequisites(self) -> Iterable[Prerequisite]:
            return []

        def perform(self) -> Iterable[Action]:
            return []

    def test_return_code(self):
        test_unit = TestSubprocessAction.SubprocessActionHarness(Path("beef"))
        assert test_unit.executable == Path("beef")

    def test_run_process(self, fake_process: FakeProcess):
        test_unit = TestSubprocessAction.SubprocessActionHarness(Path("true"))
        recorder = fake_process.register(["true"], returncode=0)
        test_unit.run_subprocess()
        assert recorder.call_count() == 1

    def test_run_process_failure(self, fake_process: FakeProcess):
        test_unit = TestSubprocessAction.SubprocessActionHarness(Path("false"))
        recorder = fake_process.register(["false"], returncode=1)
        with raises(SubprocessActionException):
            test_unit.run_subprocess()
        assert recorder.call_count() == 1

    @mark.parametrize(
        ["creation_arguments", "run_arguments"],
        [
            (None, None),
            (["Fish", None]),
            ([None, ["Cheese"]]),
            (["Beef"], ["Turkey"]),
            (["foo", "bar"], ["bax", "qux"]),
        ],
    )
    def test_process_arguments(
        self,
        creation_arguments: list[str] | None,
        run_arguments: list[str] | None,
        fake_process: FakeProcess,
    ):
        expected = ["command"]
        if creation_arguments is None:
            test_unit = TestSubprocessAction.SubprocessActionHarness(Path("command"))
        else:  # creation_arguments is not None
            test_unit = TestSubprocessAction.SubprocessActionHarness(
                Path("command"), creation_arguments
            )
            expected.extend(creation_arguments)
        assert test_unit.executable == Path("command")

        if run_arguments is not None:
            expected.extend(run_arguments)
        recorder = fake_process.register(expected)

        if run_arguments is None:
            test_unit.run_subprocess()
        else:  # run_arguments is not None
            test_unit.run_subprocess(additional_arguments=run_arguments)
        assert recorder.call_count() == 1

    def test_directory(self, fake_process: FakeProcess):
        test_unit = TestSubprocessAction.SubprocessActionHarness(Path("directory"))
        recorder = fake_process.register(["directory"])
        test_unit.run_subprocess(directory=Path("/var/tmp"))
        assert recorder.call_count() == 1
        assert recorder.calls[0].kwargs is not None
        assert recorder.calls[0].kwargs["cwd"] == Path("/var/tmp")

    @mark.parametrize(["ranks"], [(1,), (4,)])
    def test_mpi(self, ranks: int, fake_process: FakeProcess):
        test_unit = TestSubprocessAction.SubprocessActionHarness(
            Path("parallel"), mpi=ranks
        )
        assert test_unit.executable == Path("parallel")

        recorder = fake_process.register(["mpiexec", "-n", str(ranks), "parallel"])
        test_unit.run_subprocess()
        assert recorder.call_count() == 1

    @mark.parametrize(["ranks"], [(-1,), (0,)])
    def test_mpi_bad(self, ranks: int):
        with raises(ValueError):
            TestSubprocessAction.SubprocessActionHarness(Path("parallel"), mpi=ranks)

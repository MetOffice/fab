##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from common import CompareConsoleWithFile, RunFab, RunExec, RunDump

TEST_PATH = Path('system-tests/FortranPreProcess')


def test_fab_stay():
    command = RunFab(
        TEST_PATH,
        'stay_or_go_now',
        fpp_flags='-DSHOULD_I_STAY=yes')
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='stay')
    comparison.run()


def test_exec_stay():
    command = RunExec(TEST_PATH)
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='stay')
    comparison.run()


def test_dump_stay():
    command = RunDump(TEST_PATH)
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='stay')
    comparison.run()


def test_fab_go():
    command = RunFab(
        TEST_PATH,
        'stay_or_go_now')
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='go')
    comparison.run()


def test_exec_go():
    command = RunExec(TEST_PATH)
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='go')
    comparison.run()


def test_dump_go():
    command = RunDump(TEST_PATH)
    comparison = CompareConsoleWithFile(
        command,
        expectation_suffix='go')
    comparison.run()

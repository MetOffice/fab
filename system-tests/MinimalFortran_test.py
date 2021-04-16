##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from common import CompareConsoleWithFile, RunFab, RunExec, RunDump

TEST_PATH = Path('system-tests/MinimalFortran')


def test_fab():
    command = RunFab(TEST_PATH, 'test')
    comparison = CompareConsoleWithFile(command)
    comparison.run()


def test_exec():
    command = RunExec(TEST_PATH)
    comparison = CompareConsoleWithFile(command)
    comparison.run()


def test_dump():
    command = RunDump(TEST_PATH)
    comparison = CompareConsoleWithFile(command)
    comparison.run()

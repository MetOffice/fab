##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from common import CompareFileTrees, RunGrab

TEST_PATH = Path('system-tests/GitRepository')


def test_grab():
    # TODO: I can't test with the Git protocol as for some reason the
    #       Git daemon isn't installed.
    command = RunGrab(TEST_PATH, 'git', 'file')
    comparison = CompareFileTrees(command)
    comparison.run()

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from common import CompareFileTrees, RunGrab

TEST_PATH = Path('system-tests') / Path(__file__).name.split('_test.py')[0]


def test_grab_file():
    command = RunGrab(TEST_PATH, 'svn', 'file')
    comparison = CompareFileTrees(command)
    comparison.run()


def test_grab_svn():
    command = RunGrab(TEST_PATH, 'svn', 'svn')
    comparison = CompareFileTrees(command)
    comparison.run()

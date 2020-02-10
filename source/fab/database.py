##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
Working state which is either per-build or persistent between builds.
'''
import sqlite3
from pathlib import Path
from typing import List, Any


class WorkingStateException(Exception):
    pass


class WorkingState(object):
    '''
    Provides a semi-permanent store of working state.

    Backed by a database which may be deleted at any point. It should not be
    used for permanent storage of e.g. configuration.
    '''
    def __init__(self, working_directory: Path):
        self._working_directory = working_directory

        if not self._working_directory.exists():
            self._working_directory.mkdir(parents=True)

        self._connection = sqlite3.connect(str(working_directory / 'state.db'))
        self._connection.row_factory = sqlite3.Row

    def __del__(self):
        self._connection.close()

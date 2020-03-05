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


class WorkingStateException(Exception):
    pass


class StateDatabase(object):
    '''
    Provides a semi-permanent store of working state.

    Backed by a database which may be deleted at any point. It should not be
    used for permanent storage of e.g. configuration.
    '''
    def __init__(self, working_directory: Path):
        self._working_directory: Path = working_directory

        if not self._working_directory.exists():
            self._working_directory.mkdir(parents=True)

        self.connection: sqlite3.Connection \
            = sqlite3.connect(str(working_directory / 'state.db'))
        self.connection.row_factory = sqlite3.Row

    def __del__(self):
        self.connection.close()

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Core of the source extraction tool.
"""

from pathlib import Path
from typing import Sequence


class Grab(object):
    def __init__(self, workspace: Path):
        self._workspace = workspace

    def run(self, repositories: Sequence[str]) -> None:
        pass

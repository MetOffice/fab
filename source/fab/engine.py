##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from typing import List
from fab.artifact import Artifact


class Engine(object):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        pass

    def process(self, artifact: Artifact) -> List[Artifact]:
        print(f"Given artifact: {artifact.location}")
        return []

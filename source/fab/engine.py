##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from typing import List
from fab.artifact import Artifact


class Engine(object):
    def __init__(self) -> None:
        pass

    def process(self, artifact: Artifact) -> List[Artifact]:
        print(f"Given artifact: {artifact.location}")
        return []

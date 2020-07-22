##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

import re
from pathlib import Path
from typing import \
    List, \
    Mapping, \
    Tuple, \
    Type
from fab.artifact import \
    Artifact, \
    FileType, \
    State, \
    New, \
    Unknown, \
    Seen, \
    Raw
from fab.tasks import Task


class PathMap(object):
    def __init__(self,
                 pattern: str,
                 filetype: Type[FileType],
                 state: Type[State]):
        self._pattern = pattern
        self._filetype = filetype
        self._state = state

    @property
    def pattern(self):
        return self._pattern

    @property
    def filetype(self):
        return self._filetype

    @property
    def state(self):
        return self._state

    def match(self, path: Path) -> bool:
        matched = False
        if re.match(self.pattern, str(path)):
            matched = True
        return matched


class Engine(object):
    def __init__(self,
                 workspace: Path,
                 pathmaps: List[PathMap],
                 taskmap: Mapping[
                     Tuple[Type[FileType], Type[State]],
                     Task]) -> None:
        self._workspace = workspace
        self._pathmaps = pathmaps
        self._taskmap = taskmap

    def process(self, artifact: Artifact) -> List[Artifact]:

        new_artifacts = []
        # Identify tasks that are completely new
        if (artifact.state is New
                and artifact.filetype is Unknown):
            # Use the pathmap list to work out the
            # filetype and starting state
            new_artifact = None
            for pathmap in self._pathmaps:
                if pathmap.match(artifact.location):
                    new_artifact = Artifact(artifact.location,
                                            pathmap.filetype,
                                            pathmap.state)
            # Assuming we found a match and were able
            # to create the artifact, return it so that
            # it can be added to the queue
            if new_artifact is not None:
                # TODO: Calculate hash of file here
                # new_artifact.set_hash(hash)
                new_artifacts.append(new_artifact)

        else:
            # An artifact with a filetype and state set
            # will have an appropriate task that should
            # be used to run it (though unlike the old
            # implementation this is probably returning
            # the instance of the Task not the class)
            task = self._taskmap[(artifact.filetype,
                                  artifact.state)]
            # TODO: Execute the task on the artifact
            # here and prepare a new output artifact
            # if isinstance(task, Analyser):
            #    new_artifacts.append(task.run(artifact.location))
            print(f"Would process {artifact.location} "
                  f"here using {task}")

            # Pretending a preprocess step has been done:
            if artifact.state is Seen:
                new_artifact = Artifact(
                    artifact.location.with_suffix(".f90"),
                    artifact.filetype,
                    Raw)
                new_artifacts.append(new_artifact)

        return new_artifacts

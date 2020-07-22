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
    Analysed
from fab.tasks import Task
from fab.tasks.common import HashCalculator
from fab.database import SqliteStateDatabase


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
        self._database = SqliteStateDatabase(workspace)

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
                # TODO: Perhaps the HashCalculator doesn't need
                # to be a Task at all anymore...?
                hash_calculator = HashCalculator(self._database)
                hash_calculator.run(new_artifact)
                new_artifacts.append(new_artifact)

        elif artifact.state is Analysed:
            # Analysed tasks are ready to be compiled, but
            # they will be unordered;

            # We need a new structure which keeps
            # track of what Analysed files are in the
            # system; whether they are needed by one
            # of our targets, and whether they have
            # been compiled, we will call this the scoreboard

            #  1. Find out what units/symbols are in
            #     this Artifact (either a database lookup
            #     or an attribute of the Artifact?)
            #  2. If None of these are on the scoreboard
            #     then put the Artifact back on the queue
            #     (we don't know if it is needed yet)
            #  3. If one or more *are* on the scoreboard
            #     i.   Add this Artifact to the scoreboard
            #          in an "Analysed" state
            #     ii.  Add each of its dependencies to the
            #          scoreboard in "Heard of" state if
            #          it isn't on the board already
            #     iii. If all of its dependencies are on
            #          the board in a "Compiled" state
            #          then compile the Artifact.
            #          If not then put it back on the
            #          queue again
            print(f'Looking at {artifact.location}')
            print(f'    Defines   : {artifact.defines}')
            print(f'    Depends on: {artifact.depends_on}')
            pass

        else:
            # An artifact with a filetype and state set
            # will have an appropriate task that should
            # be used to run it (though unlike the old
            # implementation this is probably returning
            # the instance of the Task not the class)
            if ((artifact.filetype, artifact.state)
                    in self._taskmap):
                task = self._taskmap[(artifact.filetype,
                                      artifact.state)]

                new_artifacts.extend(task.run(artifact))
            else:
                print("Nothing defined in Task map for "
                      f"{artifact.filetype}, {artifact.state}")

        return new_artifacts

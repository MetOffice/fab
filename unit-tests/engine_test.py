##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from typing import List, Mapping, Tuple, Type

from fab.engine import PathMap, Engine
from fab.artifact import Artifact, State, FileType, Unknown, New
from fab.tasks import Task


class DummyState(State):
    pass


class DummyFileType(FileType):
    pass


class DummyState2(State):
    pass


class DummyFileType2(FileType):
    pass


class DummyTask(Task):
    def run(self, artifacts: List[Artifact]):
        new_artifact = Artifact(artifacts[0].location.with_suffix('.bar'),
                                DummyFileType2,
                                DummyState2)
        return [new_artifact]


class DummyLock(object):
    def acquire(self):
        pass

    def release(self):
        pass


class TestPathMap:
    def test_constructor(self):
        pattern = r'.*abcd.*'
        pathmap = PathMap(pattern,
                          DummyFileType,
                          DummyState)
        assert pathmap.pattern == pattern
        assert pathmap.filetype is DummyFileType
        assert pathmap.state is DummyState

    def test_contains(self):
        pattern = r'.*abcd.*'
        pathmap = PathMap(pattern,
                          DummyFileType,
                          DummyState)
        matching = 'foo_abcd_bar'
        failing = 'foo_efgh_bar'
        assert matching in pathmap
        assert failing not in pathmap


class TestEngine:
    def test_process(self, tmp_path: Path):
        pattern = r'.*\.foo'
        pathmap = PathMap(pattern,
                          DummyFileType,
                          DummyState)

        taskmap: Mapping[Tuple[Type[FileType], Type[State]], Task] = {
            (DummyFileType, DummyState): DummyTask(),
        }
        engine = Engine(tmp_path,
                        "test_target",
                        [pathmap],
                        taskmap)

        assert engine.target == "test_target"

        test_path = tmp_path / "test.foo"
        test_path.write_text("This is the Engine test")
        artifact = Artifact(test_path,
                            Unknown,
                            New)

        discovery: Mapping[str, str] = {}
        objects: List[str] = []
        lock = DummyLock()

        new_artifact = engine.process(artifact,
                                      discovery,
                                      objects,
                                      lock)

        assert len(new_artifact) == 1
        assert new_artifact[0].location == artifact.location
        assert new_artifact[0].filetype is DummyFileType
        assert new_artifact[0].state is DummyState
        assert new_artifact[0]._hash == 1630603340
        assert discovery == {}
        assert objects == []

        new_artifact2 = engine.process(new_artifact[0],
                                       discovery,
                                       objects,
                                       lock)

        assert len(new_artifact2) == 1
        assert new_artifact2[0].location == tmp_path / "test.bar"
        assert new_artifact2[0].filetype is DummyFileType2
        assert new_artifact2[0].state is DummyState2
        assert new_artifact2[0]._hash is None
        assert discovery == {}
        assert objects == []

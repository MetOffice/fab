##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

from pathlib import Path
from fab.artifact import Artifact, New, Unknown


class TestArtifact:
    def test_constructor(self):
        test_path = Path('/test/path')
        artifact = Artifact(test_path,
                            Unknown,
                            New)

        assert artifact.location == test_path
        assert artifact.state is New
        assert artifact.filetype is Unknown
        assert artifact.depends_on == []
        assert artifact.defines == []

    def test_hash(self, tmp_path: Path):
        test_path = Path(tmp_path / 'test.foo')
        test_path.write_text("Lorem ipsum dolor sit")
        expected_hash = 1463158782
        artifact = Artifact(test_path,
                            Unknown,
                            New)
        assert artifact.hash == expected_hash
        # Check that it is cached
        test_path.unlink()
        assert artifact.hash == expected_hash

    def test_add_string_dependency(self):
        test_path = Path('/test/path')
        artifact = Artifact(test_path,
                            Unknown,
                            New)
        artifact.add_dependency("foo")
        assert artifact.depends_on == ["foo"]

    def test_add_path_dependency(self):
        test_path = Path('/test/path')
        artifact = Artifact(test_path,
                            Unknown,
                            New)
        dep = Path('/path/to/bar')
        artifact.add_dependency(dep)
        assert artifact.depends_on == [dep]

    def test_add_definition(self):
        test_path = Path('/test/path')
        artifact = Artifact(test_path,
                            Unknown,
                            New)
        artifact.add_definition("bar")
        assert artifact.defines == ["bar"]

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path

from fab.tasks.common import Linker
from fab.artifact import \
    Artifact, \
    New, \
    Unknown, \
    Executable, \
    Linked


class TestLinker:
    def test_run(self, mocker, tmp_path: Path):
        # Instantiate Linker
        workspace = Path(tmp_path)
        linker = Linker('foo',
                        ['--bar', '--baz'],
                        workspace,
                        'qux')

        # Create artifacts (object files for linking)
        file1 = '/path/to/file.1'
        file2 = '/path/to/file.2'
        artifacts = [Artifact(Path(file1),
                              Unknown,
                              New),
                     Artifact(Path(file2),
                              Unknown,
                              New)]

        # Monkeypatch the subprocess call out and run linker
        patched_run = mocker.patch('subprocess.run')
        artifacts_out = linker.run(artifacts)

        # Check that the subprocess call contained the command
        # that we would expect based on the above
        expected_command = ['foo',
                            '-o',
                            str(workspace / 'qux'),
                            file1,
                            file2,
                            '--bar',
                            '--baz']
        patched_run.assert_called_once_with(expected_command,
                                            check=True)
        assert len(artifacts_out) == 1
        assert artifacts_out[0].location == workspace / 'qux'
        assert artifacts_out[0].filetype is Executable
        assert artifacts_out[0].state is Linked
        assert artifacts_out[0].depends_on == []
        assert artifacts_out[0].defines == []

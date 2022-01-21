"""
Test CCompiler.

"""
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from fab.tasks.c import CCompiler


class Test_Compiler(object):

    def test_vanilla(self):
        # ensure the command is formed correctly
        mock_flags_config = Mock()
        mock_flags_config.flags_for_path.return_value = ['-I', 'foo/bar', '-Dhello']
        c_compiler = CCompiler(compiler=['gcc', '-c'], flags=mock_flags_config, workspace=Path("workspace"))

        analysed_file = Mock(fpath=Path("foo.c"))

        # with mock.patch('subprocess.run') as mock_run:
        with mock.patch('fab.tasks.c.run_command') as mock_run:
            c_compiler.run(analysed_file)
            mock_run.assert_called_with(['gcc', '-c', '-I', 'foo/bar', '-Dhello', 'foo.c', '-o', 'foo.o'])

"""
Test CCompiler.

"""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fab.config import AddFlags
from fab.dep_tree import AnalysedFile
from fab.steps.compile_c import CompileC


class Test_Compiler(object):

    def test_vanilla(self):
        # ensure the command is formed correctly

        # config = mock.Mock(workspace=Path('foo/src'), use_multiprocessing=False)
        config = SimpleNamespace(workspace=Path('foo/src'), use_multiprocessing=False)

        c_compiler = CompileC(
            compiler='gcc', common_flags=['-c'], path_flags=[
                AddFlags(match='foo/src/*', flags=['-I', 'foo/include', '-Dhello'])])

        analysed_files = {Path('foo/src/foo.c'): AnalysedFile(fpath=Path('foo/src/foo.c'), file_hash=None)}

        with mock.patch('fab.steps.compile_c.run_command') as mock_run:
            c_compiler.run(artefact_store={'build_tree': analysed_files}, config=config)
            mock_run.assert_called_with([
                'gcc', '-c', '-I', 'foo/include', '-Dhello', 'foo/src/foo.c', '-o', 'foo/src/foo.o'])

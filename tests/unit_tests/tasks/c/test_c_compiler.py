"""
Test CCompiler.

"""
from pathlib import Path
from unittest import mock

from fab.build_config import AddFlags, BuildConfig
from fab.constants import BUILD_TREES
from fab.dep_tree import AnalysedFile
from fab.steps.compile_c import CompileC

# TODO: THIS SHOULD BE IN THE STEPS FOLDER, NOT TASKS


class Test_Compiler(object):

    def test_vanilla(self):
        # ensure the command is formed correctly

        config = BuildConfig('proj', fab_workspace=Path('/fab_workspace'),
                             multiprocessing=False, reuse_artefacts=False)

        c_compiler = CompileC(
            compiler='gcc', common_flags=['-c'], path_flags=[
                AddFlags(match='foo/src/*', flags=['-I', 'foo/include', '-Dhello'])])

        analysed_files = {Path('foo/src/foo.c'): AnalysedFile(fpath=Path('foo/src/foo.c'), file_hash=None)}

        with mock.patch('fab.steps.compile_c.run_command') as mock_run:
            with mock.patch('pathlib.Path.mkdir'):
                with mock.patch('fab.steps.compile_c.send_metric'):
                    c_compiler.run(artefact_store={BUILD_TREES: {None: analysed_files}}, config=config)
                    mock_run.assert_called_with([
                        'gcc', '-c', '-I', 'foo/include', '-Dhello', 'foo/src/foo.c', '-o', 'foo/src/foo.o'])

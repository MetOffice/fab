from os.path import normpath
from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import AddFlags, BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.dep_tree import AnalysedFile
from fab.steps.compile_c import CompileC


# This is more of an integration test than a unit test
class Test_CompileC(object):

    def test_vanilla(self):
        # ensure the command is formed correctly

        # prepare a compiler step
        config = BuildConfig('proj', source_root=Path('foo/src'), multiprocessing=False)
        analysed_file = AnalysedFile(fpath=Path('foo/src/foo.c'), file_hash=0)
        artefact_store = {BUILD_TREES: {None: {analysed_file.fpath: analysed_file}}}
        c_compiler = CompileC(path_flags=[
            AddFlags(match='foo/src/*', flags=['-I', 'foo/include', '-Dhello'])])

        # run the step
        with mock.patch('fab.steps.compile_c.run_command') as mock_run_command:
            with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                with mock.patch('pathlib.Path.mkdir'):
                    c_compiler.run(artefact_store=artefact_store, config=config)

        # ensure it made the correct command-line call from the child process
        mock_run_command.assert_called_with([
            'gcc', '-c', '-I', 'foo/include', '-Dhello',
            normpath('foo/src/foo.c'), '-o', normpath('foo/src/foo.o'),
        ])

        # ensure it sent a metric from the child process
        mock_send_metric.assert_called_once()

        # ensure it created the correct artefact collection
        assert artefact_store[OBJECT_FILES] == {
            None: {analysed_file.fpath.with_suffix('.o'), }
        }

    def test_exception_handling(self):

        # prepare a compiler step
        config = BuildConfig('proj', source_root=Path('foo/src'), multiprocessing=False)
        analysed_file = AnalysedFile(fpath=Path('foo/src/foo.c'), file_hash=0)
        artefact_store = {BUILD_TREES: {None: {analysed_file.fpath: analysed_file}}}
        c_compiler = CompileC()

        # mock the run command to raise
        with pytest.raises(RuntimeError):
            with mock.patch('fab.steps.compile_c.run_command', side_effect=Exception):
                with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                    with mock.patch('pathlib.Path.mkdir'):
                        c_compiler.run(artefact_store=artefact_store, config=config)

        # ensure no metric was sent from the child process
        mock_send_metric.assert_not_called()

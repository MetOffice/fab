import os
from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import AddFlags, BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.parse import AnalysedFile
from fab.parse.c import AnalysedC
from fab.steps.compile_c import CompileC


@pytest.fixture
def content(tmp_path):
    config = BuildConfig('proj', multiprocessing=False, fab_workspace=tmp_path)
    analysed_file = AnalysedC(fpath=Path(f'{config.source_root}/foo.c'), file_hash=0)
    with mock.patch.dict(os.environ, {'CC': 'foo_cc', 'CFLAGS': '-Denv_flag'}):
        with mock.patch('fab.steps.compile_c.get_compiler_version', return_value='1.2.3'):
            compiler = CompileC(path_flags=[
                AddFlags(match='$source/*', flags=['-I', 'foo/include', '-Dhello'])])
    artefact_store = {BUILD_TREES: {None: {analysed_file.fpath: analysed_file}}}
    expect_hash = 9120682468
    return config, artefact_store, compiler, analysed_file, expect_hash


# This is more of an integration test than a unit test
class Test_CompileC(object):

    def test_vanilla(self, content):
        # ensure the command is formed correctly
        config, artefact_store, compiler, analysed_file, expect_hash = content

        # run the step
        with mock.patch('fab.steps.compile_c.run_command') as mock_run_command:
            with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                with mock.patch('pathlib.Path.mkdir'):
                    compiler.run(artefact_store=artefact_store, config=config)

        # ensure it made the correct command-line call from the child process
        mock_run_command.assert_called_with([
            'foo_cc', '-c', '-Denv_flag', '-I', 'foo/include', '-Dhello',
            f'{config.source_root}/foo.c', '-o', str(config.prebuild_folder / f'foo.{expect_hash:x}.o'),
        ])

        # ensure it sent a metric from the child process
        mock_send_metric.assert_called_once()

        # ensure it created the correct artefact collection
        assert artefact_store[OBJECT_FILES] == {
            None: {config.prebuild_folder / f'foo.{expect_hash:x}.o', }
        }

    def test_exception_handling(self, content):
        config, artefact_store, compiler, _, _ = content

        # mock the run command to raise
        with pytest.raises(RuntimeError):
            with mock.patch('fab.steps.compile_c.run_command', side_effect=Exception):
                with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                    with mock.patch('pathlib.Path.mkdir'):
                        compiler.run(artefact_store=artefact_store, config=config)

        # ensure no metric was sent from the child process
        mock_send_metric.assert_not_called()


class Test_get_obj_combo_hash(object):

    def test_vanilla(self, content):
        config, artefact_store, compiler, analysed_file, expect_hash = content

        flags = compiler.flags.flags_for_path(analysed_file.fpath, config)
        result = compiler._get_obj_combo_hash(analysed_file, flags)

        assert result == expect_hash

    def test_change_file(self, content):
        config, artefact_store, compiler, analysed_file, expect_hash = content
        analysed_file._file_hash += 1

        flags = compiler.flags.flags_for_path(analysed_file.fpath, config)
        result = compiler._get_obj_combo_hash(analysed_file, flags)

        assert result == expect_hash + 1

    def test_change_flags(self, content):
        config, artefact_store, compiler, analysed_file, expect_hash = content
        compiler.flags.common_flags.append('-Dfoo')

        flags = compiler.flags.flags_for_path(analysed_file.fpath, config)
        result = compiler._get_obj_combo_hash(analysed_file, flags)

        assert result != expect_hash

    def test_change_compiler(self, content):
        config, artefact_store, compiler, analysed_file, expect_hash = content
        compiler.compiler = 'ooh_cc'

        flags = compiler.flags.flags_for_path(analysed_file.fpath, config)
        result = compiler._get_obj_combo_hash(analysed_file, flags)

        assert result != expect_hash

    def test_change_compiler_version(self, content):
        config, artefact_store, compiler, analysed_file, expect_hash = content
        compiler.compiler_version = '1.2.4'

        flags = compiler.flags.flags_for_path(analysed_file.fpath, config)
        result = compiler._get_obj_combo_hash(analysed_file, flags)

        assert result != expect_hash

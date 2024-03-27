import os
from pathlib import Path
from unittest import mock
from unittest.mock import DEFAULT

import pytest

from fab.build_config import AddFlags, BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.parse.c import AnalysedC
from fab.steps.compile_c import _get_obj_combo_hash, compile_c


@pytest.fixture
def content(tmp_path):
    config = BuildConfig('proj', multiprocessing=False, fab_workspace=tmp_path)

    analysed_file = AnalysedC(fpath=Path(f'{config.source_root}/foo.c'), file_hash=0)
    config._artefact_store[BUILD_TREES] = {None: {analysed_file.fpath: analysed_file}}
    expect_hash = 9120682468
    return config, analysed_file, expect_hash


# This is more of an integration test than a unit test
class Test_CompileC(object):

    def test_vanilla(self, content):
        # ensure the command is formed correctly
        config, analysed_file, expect_hash = content

        # run the step
        with mock.patch.multiple(
                'fab.steps.compile_c',
                run_command=DEFAULT,
                send_metric=DEFAULT,
                get_compiler_version=mock.Mock(return_value='1.2.3')) as values:
            with mock.patch('pathlib.Path.mkdir'):
                with mock.patch.dict(os.environ, {'CC': 'foo_cc', 'CFLAGS': '-Denv_flag'}), \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    compile_c(
                        config=config, path_flags=[AddFlags(match='$source/*', flags=['-I', 'foo/include', '-Dhello'])])

        # ensure it made the correct command-line call from the child process
        values['run_command'].assert_called_with([
            'foo_cc', '-c', '-Denv_flag', '-I', 'foo/include', '-Dhello',
            f'{config.source_root}/foo.c', '-o', str(config.prebuild_folder / f'foo.{expect_hash:x}.o'),
        ])

        # ensure it sent a metric from the child process
        values['send_metric'].assert_called_once()

        # ensure it created the correct artefact collection
        assert config._artefact_store[OBJECT_FILES] == {
            None: {config.prebuild_folder / f'foo.{expect_hash:x}.o', }
        }

    def test_exception_handling(self, content):
        config, _, _ = content

        # mock the run command to raise
        with pytest.raises(RuntimeError):
            with mock.patch('fab.steps.compile_c.run_command', side_effect=Exception):
                with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                    with mock.patch('pathlib.Path.mkdir'):
                        compile_c(config=config)

        # ensure no metric was sent from the child process
        mock_send_metric.assert_not_called()


class Test_get_obj_combo_hash(object):

    @pytest.fixture
    def flags(self):
        return ['-c', '-Denv_flag', '-I', 'foo/include', '-Dhello']

    def test_vanilla(self, content, flags):
        _, analysed_file, expect_hash = content
        result = _get_obj_combo_hash('foo_cc', '1.2.3', analysed_file, flags)
        assert result == expect_hash

    def test_change_file(self, content, flags):
        _, analysed_file, expect_hash = content
        analysed_file._file_hash += 1
        result = _get_obj_combo_hash('foo_cc', '1.2.3', analysed_file, flags)
        assert result == expect_hash + 1

    def test_change_flags(self, content, flags):
        _, analysed_file, expect_hash = content
        flags = ['-Dfoo'] + flags
        result = _get_obj_combo_hash('foo_cc', '1.2.3', analysed_file, flags)
        assert result != expect_hash

    def test_change_compiler(self, content, flags):
        _, analysed_file, expect_hash = content
        result = _get_obj_combo_hash('ooh_cc', '1.2.3', analysed_file, flags)
        assert result != expect_hash

    def test_change_compiler_version(self, content, flags):
        _, analysed_file, expect_hash = content
        result = _get_obj_combo_hash('foo_cc', '1.2.4', analysed_file, flags)
        assert result != expect_hash

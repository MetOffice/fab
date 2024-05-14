# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''Tests the compile_c.py step.
'''

import os
from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import AddFlags, BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.parse.c import AnalysedC
from fab.steps.compile_c import _get_obj_combo_hash, compile_c
from fab.tools import Categories, Flags


# This avoids pylint warnings about Redefining names from outer scope
@pytest.fixture(name="content")
def fixture_content(tmp_path, tool_box):
    '''Provides a test environment consisting of a config instance,
    analysed file and expected hash.'''

    config = BuildConfig('proj', tool_box, multiprocessing=False,
                         fab_workspace=tmp_path)

    analysed_file = AnalysedC(fpath=Path(f'{config.source_root}/foo.c'), file_hash=0)
    config._artefact_store[BUILD_TREES] = {None: {analysed_file.fpath: analysed_file}}
    expect_hash = 7435424994
    return config, analysed_file, expect_hash


# This is more of an integration test than a unit test
class TestCompileC():
    '''Test various functionalities of the C compilation step.'''

    def test_vanilla(self, content):
        '''Ensure the command is formed correctly.'''
        config, _, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]

        # run the step
        with mock.patch("fab.steps.compile_c.send_metric") as send_metric:
            with mock.patch('pathlib.Path.mkdir'):
                with mock.patch.dict(os.environ, {'CFLAGS': '-Denv_flag'}), \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, "
                                                     "cannot send metrics"):
                    compile_c(config=config,
                              path_flags=[AddFlags(match='$source/*',
                                                   flags=['-I', 'foo/include', '-Dhello'])])

        # ensure it made the correct command-line call from the child process
        compiler.run.assert_called_with(
            cwd=Path(config.source_root),
            additional_parameters=['-c', '-Denv_flag', '-I', 'foo/include',
                                   '-Dhello', 'foo.c',
                                   '-o', str(config.prebuild_folder /
                                             f'foo.{expect_hash:x}.o')],
        )

        # ensure it sent a metric from the child process
        send_metric.assert_called_once()

        # ensure it created the correct artefact collection
        assert config.artefact_store[OBJECT_FILES] == {
            None: {config.prebuild_folder / f'foo.{expect_hash:x}.o', }
        }

    def test_exception_handling(self, content):
        '''Test exception handling if the compiler fails.'''
        config, _, _ = content
        compiler = config.tool_box[Categories.C_COMPILER]
        # mock the run command to raise an exception
        with pytest.raises(RuntimeError):
            with mock.patch.object(compiler, "run", side_effect=Exception):
                with mock.patch('fab.steps.compile_c.send_metric') as mock_send_metric:
                    with mock.patch('pathlib.Path.mkdir'):
                        compile_c(config=config)

        # ensure no metric was sent from the child process
        mock_send_metric.assert_not_called()


class TestGetObjComboHash():
    '''Tests the object combo hash functionality.'''

    @pytest.fixture
    def flags(self):
        '''Returns the flag for these tests.'''
        return Flags(['-Denv_flag', '-I', 'foo/include', '-Dhello'])

    def test_vanilla(self, content, flags):
        '''Test that we get the expected hashes in this test setup.'''
        config, analysed_file, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]
        result = _get_obj_combo_hash(compiler, analysed_file, flags)
        assert result == expect_hash

    def test_change_file(self, content, flags):
        '''Check that a change in the file (simulated by changing
        the hash) changes the obj combo hash.'''
        config, analysed_file, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]
        analysed_file._file_hash += 1
        result = _get_obj_combo_hash(compiler, analysed_file, flags)
        assert result == expect_hash + 1

    def test_change_flags(self, content, flags):
        '''Test that changing the flags changes the hash.'''
        config, analysed_file, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]
        flags = Flags(['-Dfoo'] + flags)
        result = _get_obj_combo_hash(compiler, analysed_file, flags)
        assert result != expect_hash

    def test_change_compiler(self, content, flags):
        '''Test that a change in the name of the compiler changes
        the hash.'''
        config, analysed_file, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]
        # Change the name of the compiler
        compiler._name = compiler.name + "XX"
        result = _get_obj_combo_hash(compiler, analysed_file, flags)
        assert result != expect_hash

    def test_change_compiler_version(self, content, flags):
        '''Test that a change in the version number of the compiler
        changes the hash.'''
        config, analysed_file, expect_hash = content
        compiler = config.tool_box[Categories.C_COMPILER]
        compiler._version = "9.8.7"
        result = _get_obj_combo_hash(compiler, analysed_file, flags)
        assert result != expect_hash

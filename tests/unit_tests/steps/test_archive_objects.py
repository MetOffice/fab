##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Test for the archive step.
"""

from unittest import mock
from unittest.mock import call

import pytest

from fab.artefacts import ArtefactSet
from fab.build_config import BuildConfig
from fab.steps.archive_objects import archive_objects
from fab.tools import Category, ToolBox


class TestArchiveObjects:
    '''Test the achive step.
    '''

    def test_for_exes(self):
        '''As used when archiving before linking exes.
        '''
        targets = ['prog1', 'prog2']

        config = BuildConfig('proj', ToolBox())
        for target in targets:
            config.artefact_store.update_dict(
                ArtefactSet.OBJECT_FILES, target,
                set([f'{target}.o', 'util.o']))

        mock_result = mock.Mock(returncode=0, return_value=123)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as mock_run_command, \
                pytest.warns(UserWarning, match="_metric_send_conn not set, "
                                                "cannot send metrics"):
            archive_objects(config=config)

        # ensure the correct command line calls were made
        expected_calls = [
            call(['ar', 'cr', str(config.build_output / f'{target}.a'),
                  f'{target}.o', 'util.o'],
                 capture_output=True, env=None, cwd=None, check=False)
            for target in targets
        ]
        mock_run_command.assert_has_calls(expected_calls)

        # ensure the correct artefacts were created
        assert config.artefact_store[ArtefactSet.OBJECT_ARCHIVES] == {
            target: set([str(config.build_output / f'{target}.a')])
            for target in targets}

    def test_for_library(self):
        '''As used when building an object archive or archiving before linking
        a shared library.
        '''

        # Make sure that 'ar' is initialised, which means `ar --version` was
        # called. Otherwise (esp. in parallel runs) the test below can report
        # two calls, the first one to determine the version. Note that the
        # previous tests has does not have this problem since it uses
        # `assert_has_calls`. It is sufficient to just get ar from a ToolBox,
        # this will make sure ar actually works, so `ar --version` is called.
        tool_box = ToolBox()
        _ = tool_box.get_tool(Category.AR)

        config = BuildConfig('proj', tool_box)
        config.artefact_store.update_dict(
            ArtefactSet.OBJECT_FILES, None, {'util1.o', 'util2.o'})

        mock_result = mock.Mock(returncode=0, return_value=123)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as mock_run_command, \
                pytest.warns(UserWarning, match="_metric_send_conn not set, "
                                                "cannot send metrics"):
            archive_objects(config=config,
                            output_fpath=config.build_output / 'mylib.a')

        # ensure the correct command line calls were made
        mock_run_command.assert_called_once_with([
            'ar', 'cr', str(config.build_output / 'mylib.a'),
            'util1.o', 'util2.o'],
            capture_output=True, env=None, cwd=None, check=False)

        # ensure the correct artefacts were created
        assert config.artefact_store[ArtefactSet.OBJECT_ARCHIVES] == {
            None: set([str(config.build_output / 'mylib.a')])}

    def test_incorrect_tool(self, tool_box):
        '''Test that an incorrect archive tool is detected
        '''

        config = BuildConfig('proj', tool_box)
        cc = tool_box.get_tool(Category.C_COMPILER, config.mpi, config.openmp)
        # And set its category to be AR
        cc._category = Category.AR
        # Now add this 'ar' tool to the tool box
        tool_box.add_tool(cc)

        with pytest.raises(RuntimeError) as err:
            archive_objects(config=config,
                            output_fpath=config.build_output / 'mylib.a')
        assert ("Unexpected tool 'mock_c_compiler' of type '<class "
                "'fab.tools.compiler.CCompiler'>' instead of Ar"
                in str(err.value))

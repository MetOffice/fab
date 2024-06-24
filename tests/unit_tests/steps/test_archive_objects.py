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
        config._artefact_store = {
            ArtefactSet.OBJECT_FILES: {target: [f'{target}.o', 'util.o']
                                       for target in targets}}

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
            target: [str(config.build_output / f'{target}.a')] for target in targets}

    def test_for_library(self):
        '''As used when building an object archive or archiving before linking
        a shared library.
        '''

        config = BuildConfig('proj', ToolBox())
        config._artefact_store = {ArtefactSet.OBJECT_FILES: {None: ['util1.o', 'util2.o']}}

        mock_result = mock.Mock(returncode=0, return_value=123)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as mock_run_command, \
                pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
            archive_objects(config=config, output_fpath=config.build_output / 'mylib.a')

        # ensure the correct command line calls were made
        mock_run_command.assert_called_once_with([
            'ar', 'cr', str(config.build_output / 'mylib.a'), 'util1.o', 'util2.o'],
            capture_output=True, env=None, cwd=None, check=False)

        # ensure the correct artefacts were created
        assert config.artefact_store[ArtefactSet.OBJECT_ARCHIVES] == {
            None: [str(config.build_output / 'mylib.a')]}

    def test_incorrect_tool(self):
        '''Test that an incorrect archive tool is detected
        '''

        config = BuildConfig('proj', ToolBox())
        tool_box = config.tool_box
        cc = tool_box[Category.C_COMPILER]
        # And set its category to C_COMPILER
        cc._category = Category.AR
        # So overwrite the C compiler with the re-categories Fortran compiler
        tool_box.add_tool(cc)

        with pytest.raises(RuntimeError) as err:
            archive_objects(config=config,
                            output_fpath=config.build_output / 'mylib.a')
        assert ("Unexpected tool 'gcc' of type '<class "
                "'fab.tools.compiler.Gcc'>' instead of Ar" in str(err.value))

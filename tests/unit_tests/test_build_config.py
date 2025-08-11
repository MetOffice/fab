# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

'''
This module tests the BuildConfig class.
'''

import os
from pathlib import Path
from unittest import mock

from fab.build_config import BuildConfig
from fab.steps import step
from fab.steps.cleanup_prebuilds import CLEANUP_COUNT
from fab.tools import ToolBox


class TestBuildConfig:
    '''
    This class tests the BuildConfig class.
    '''

    def test_error_newlines(self):
        '''
        Check cli tool errors have newlines displayed correctly.
        v0.9.0a1 displayed then as `\\n` (see #164).
        '''
        @step
        def simple_step(config):
            raise RuntimeError("foo error\n1\n2\n3")

        try:
            simple_step(None)
        except RuntimeError as err:
            assert '1\n2\n3' in str(err)

    def test_add_cleanup(self):
        '''
        Ensure the cleanup step is added.
        '''
        with BuildConfig('proj', ToolBox()) as config:
            assert CLEANUP_COUNT not in config.artefact_store

        assert CLEANUP_COUNT in config.artefact_store

    @mock.patch.dict('os.environ')
    def test_fab_workspace_no_env(self, tmpdir):
        '''
        Test that the Fab workspace is set as expected when the
        environment variable FAB_WORKSPACE is not used
        '''

        this_dir = Path.cwd()
        config = BuildConfig('proj', ToolBox())
        assert config.project_workspace == this_dir / 'fab-workspace' / 'proj'

        some_dir = Path('/some_dir')
        config = BuildConfig('proj', ToolBox(), fab_workspace=some_dir)
        assert config.project_workspace == some_dir / 'proj'

        # Test again the expected behaviour from a different directory,
        # to ensure that Fab correctly queries cwd
        os.chdir(tmpdir)
        config = BuildConfig('proj', ToolBox())
        assert config.project_workspace == tmpdir / 'fab-workspace' / 'proj'

    @mock.patch.dict('os.environ', {'FAB_WORKSPACE': '/FAB'})
    def test_fab_workspace_with_env(self):
        '''
        Test that the Fab workspace is set as expected when the environment
        variable FAB_WORKSPACE is defined.
        '''

        config = BuildConfig('proj', ToolBox())
        assert config.project_workspace == Path('/FAB') / 'proj'

        # An explicit option should overwrite FAB_WORKSPACE
        some_dir = Path('/some_dir')
        config = BuildConfig('proj', ToolBox(), fab_workspace=some_dir)
        assert config.project_workspace == some_dir / 'proj'

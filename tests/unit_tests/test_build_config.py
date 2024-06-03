# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

from fab.build_config import BuildConfig
from fab.steps import step
from fab.steps.cleanup_prebuilds import CLEANUP_COUNT
from fab.tools import ToolBox


class TestBuildConfig():

    def test_error_newlines(self, tmp_path):
        # Check cli tool errors have newlines displayed correctly.
        # v0.9.0a1 displayed then as `\\n` (see #164).
        @step
        def simple_step(config):
            raise RuntimeError("foo error\n1\n2\n3")

        try:
            simple_step(None)
        except Exception as err:
            assert '1\n2\n3' in str(err)

    def test_add_cleanup(self):
        # ensure the cleanup step is added
        with BuildConfig('proj', ToolBox()) as config:
            assert CLEANUP_COUNT not in config.artefact_store

        assert CLEANUP_COUNT in config.artefact_store

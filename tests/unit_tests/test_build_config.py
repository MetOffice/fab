# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from textwrap import dedent
from unittest import mock

from fab.parse.fortran.fortran import AnalysedFortran

from fab.build_config import BuildConfig
from fab.steps.compile_fortran import CompileFortran


class TestBuildConfig(object):

    def test_error_newlines(self, tmp_path):
        # Check cli tool errors have newlines displayed correctly.
        # v0.9.0a1 displayed then as `\\n` (see #164).
        # It's up to the various steps to insert newlines *between* their message and the tool error.
        # We're testing the general reporting mechanism here, once they get back to the top,
        # that the newlines *within* the tool error are displayed correctly.

        mock_source = {None: [AnalysedFortran('foo.f90', file_hash=0)]}

        with mock.patch('fab.steps.compile_fortran.get_compiler_version', return_value='1.2.3'):
            with mock.patch('fab.steps.compile_fortran.DEFAULT_SOURCE_GETTER', return_value=mock_source):
                config = BuildConfig('proj', fab_workspace=tmp_path, multiprocessing=False, steps=[
                    CompileFortran(compiler='foofc')])

        run_command = 'fab.steps.compile_fortran.run_command'
        err = dedent("foo error\n1\n2\n3")

        try:
            with mock.patch(run_command, side_effect=RuntimeError(err)):
                config.run()
        except Exception as err:
            assert '1\n2\n3' in str(err)

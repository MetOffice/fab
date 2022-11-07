# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from textwrap import dedent
from unittest import mock

from fab.build_config import BuildConfig
from fab.dep_tree import AnalysedFile
from fab.steps.compile_fortran import CompileFortran


class TestBuildConfig(object):

    def test_error_newlines(self, tmp_path):
        # Check cli tool errors have newlines displayed correctly (#164).
        # It's up to the various steps to insert newlines *between* their message and the tool error.
        # We're testing the general reporting mechanism here, once they get back to the top,
        # that the newlines *within* the tool error are displayed correctly.

        mock_source = {None: [AnalysedFile('foo.f', file_hash=0)]}

        with mock.patch('fab.steps.compile_fortran._get_compiler_version', return_value='1.2.3'):
            with mock.patch('fab.steps.compile_fortran.DEFAULT_SOURCE_GETTER', return_value=mock_source):
                config = BuildConfig('proj', fab_workspace=tmp_path, multiprocessing=False, steps=[
                    CompileFortran(compiler='foofc')])

        run_mp = 'fab.steps.compile_fortran.CompileFortran.run_mp'
        err = dedent("foo error\n1\n2\n3")

        try:
            with mock.patch(run_mp, return_value=[ValueError(err)]):
                config.run()
        except Exception as err:
            assert '1\n2\n3' in str(err)

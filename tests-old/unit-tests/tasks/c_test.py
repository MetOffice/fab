##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
from textwrap import dedent


class TestCPragmaInjector:
    def test_run(self, tmp_path):
        workspace = tmp_path / 'working'
        workspace.mkdir()

        test_file: Path = tmp_path / 'test.c'
        test_file.write_text(
            dedent('''
                   #include "user_include.h"
                   Unrelated text
                   #include 'another_user_include.h'
                   #include <system_include.h>
                   More unrelated text
                   #include <another_system_include.h>
                   '''))
        test_artifact = Artifact(test_file,
                                 CSource,
                                 HeadersAnalysed)
        test_artifact.add_dependency('foo')

        # Run the Injector
        injector = CPragmaInjector(workspace)
        artifacts_out = injector.run([test_artifact])

        assert len(artifacts_out) == 1
        assert artifacts_out[0].location == workspace / 'test.c'
        assert artifacts_out[0].filetype is CSource
        assert artifacts_out[0].state is Modified
        assert artifacts_out[0].depends_on == ['foo']
        assert artifacts_out[0].defines == []

        new_file = workspace / 'test.c'
        assert new_file.exists()
        with new_file.open('r') as fh:
            new_text = fh.read()

        expected_text = (
            dedent('''
                   #pragma FAB UsrIncludeStart
                   #include "user_include.h"
                   #pragma FAB UsrIncludeEnd
                   Unrelated text
                   #pragma FAB UsrIncludeStart
                   #include 'another_user_include.h'
                   #pragma FAB UsrIncludeEnd
                   #pragma FAB SysIncludeStart
                   #include <system_include.h>
                   #pragma FAB SysIncludeEnd
                   More unrelated text
                   #pragma FAB SysIncludeStart
                   #include <another_system_include.h>
                   #pragma FAB SysIncludeEnd
                   '''))

        assert new_text == expected_text

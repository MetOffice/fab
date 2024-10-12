from sys import version_info as python_version
from textwrap import dedent
from unittest import mock
from unittest.mock import mock_open

import pytest

from fab.steps.c_pragma_injector import inject_pragmas


class Test_inject_pragmas(object):

    @pytest.mark.skipif(python_version < (3, 8),
                        reason="Requires python version 3.8 or higher for "
                               "mock_open iteration")
    def test_vanilla(self):
        source = dedent(
            """
            // C++ style comment, ignore this.
            #include "user_include.h"
            #include "second_user_include.h"
            Unrelated text
            /* Including C style comment */
            #include 'another_user_include.h'
            #include <system_include.h>
            More unrelated text
            #include <another_system_include.h>
            #include "final_user_include.h"
            """
        )

        with mock.patch('fab.steps.c_pragma_injector.open',
                        mock_open(read_data=source)):
            result = inject_pragmas(fpath="foo")
            output = list(result)

        assert output == [
            '\n',
            '// C++ style comment, ignore this.\n',
            '#pragma FAB UsrIncludeStart\n',
            '#include "user_include.h"\n',
            '#pragma FAB UsrIncludeEnd\n',
            '#pragma FAB UsrIncludeStart\n',
            '#include "second_user_include.h"\n',
            '#pragma FAB UsrIncludeEnd\n',
            'Unrelated text\n',
            '/* Including C style comment */\n',
            '#pragma FAB UsrIncludeStart\n',
            "#include 'another_user_include.h'\n",
            '#pragma FAB UsrIncludeEnd\n',
            '#pragma FAB SysIncludeStart\n',
            '#include <system_include.h>\n',
            '#pragma FAB SysIncludeEnd\n',
            "More unrelated text\n",
            '#pragma FAB SysIncludeStart\n',
            '#include <another_system_include.h>\n',
            '#pragma FAB SysIncludeEnd\n',
            '#pragma FAB UsrIncludeStart\n',
            '#include "final_user_include.h"\n',
            '#pragma FAB UsrIncludeEnd\n'
        ]

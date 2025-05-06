from pathlib import Path
from textwrap import dedent

from fab.steps.c_pragma_injector import inject_pragmas


class Test_inject_pragmas(object):
    """
    Tests injection of C inclusion bracketing.
    """
    def test_vanilla(self, fs):
        """
        Tests straight forward bracketing.
        """
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
        test_file = Path('/foo.c')
        test_file.write_text(source)

        result = inject_pragmas(fpath=test_file)

        assert [line for line in result] == [
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

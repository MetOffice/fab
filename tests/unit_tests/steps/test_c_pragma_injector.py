import sys
from unittest import mock
from unittest.mock import mock_open

import pytest

from fab.steps.c_pragma_injector import inject_pragmas


class Test_inject_pragmas(object):

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher for mock_open iteration")
    def test_vanilla(self):
        input = [
            '',
            '// hi there, ignore me',
            '',
            '#include <foo>',
            '',
            '#include "bar.h"',
            '',
        ]
        data = "\n".join(input)

        with mock.patch('fab.steps.c_pragma_injector.open', mock_open(read_data=data)):
            result = inject_pragmas(fpath="foo")
            output = list(result)

        assert output == [
            '\n',
            '// hi there, ignore me\n',
            '\n',
            '#pragma FAB SysIncludeStart\n',
            '#include <foo>\n',
            '#pragma FAB SysIncludeEnd\n',
            '\n',
            '#pragma FAB UsrIncludeStart\n',
            '#include "bar.h"\n',
            '#pragma FAB UsrIncludeEnd\n',
        ]

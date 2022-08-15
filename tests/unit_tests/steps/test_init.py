import pytest

from fab.steps import check_for_errors


class Test_check_for_errors(object):

    def test_no_error(self):
        check_for_errors(['foo', 'bar'])

    def test_error(self):
        with pytest.raises(RuntimeError):
            check_for_errors(['foo', MemoryError('bar')])

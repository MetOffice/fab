##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Exercises the multi-process error helper.
"""
from pytest import raises

from fab.steps import check_for_errors


class Test_check_for_errors(object):
    """
    Tests the multi-prcoess error helper.
    """
    def test_no_error(self):
        """
        Tests the "all okay" situation.
        """
        check_for_errors(['foo', 'bar'])

    def test_error(self):
        """
        Tests the "error present" situation.
        """
        with raises(RuntimeError):
            check_for_errors(['foo', MemoryError('bar')])

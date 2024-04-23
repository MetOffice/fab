# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################

from unittest import mock

import pytest

from fab.tools import flags_checksum, run_command


class TestFlagsChecksum():

    def test_vanilla(self):
        # I think this is a poor testing pattern.
        flags = ['one', 'two', 'three', 'four']
        assert flags_checksum(flags) == 3011366051


class TestRunCommand():

    def test_no_error(self):
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.subprocess.run', return_value=mock_result):
            run_command([])

    def test_error(self):
        mock_result = mock.Mock(returncode=1)
        mocked_error_message = 'mocked error message'
        mock_result.stderr.decode = mock.Mock(return_value=mocked_error_message)
        with mock.patch('fab.tools.subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError) as err:
                run_command([])
            assert mocked_error_message in str(err.value)

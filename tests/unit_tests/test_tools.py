# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from textwrap import dedent
from unittest import mock

import pytest

from fab.tools import remove_managed_flags, flags_checksum, get_tool, get_compiler_version, run_command


class Test_remove_managed_flags(object):

    def test_gfortran(self):
        flags = ['--foo', '-J', 'nope', '--bar']
        with pytest.warns(UserWarning, match="removing managed flag"):
            result = remove_managed_flags('gfortran', flags)
        assert result == ['--foo', '--bar']

    def test_ifort(self):
        flags = ['--foo', '-module', 'nope', '--bar']
        with pytest.warns(UserWarning, match="removing managed flag"):
            result = remove_managed_flags('ifort', flags)
        assert result == ['--foo', '--bar']

    def test_unknown_compiler(self):
        flags = ['--foo', '-J', 'nope', '--bar']
        result = remove_managed_flags('foofc', flags)
        assert result == ['--foo', '-J', 'nope', '--bar']


class Test_flags_checksum(object):

    def test_vanilla(self):
        # I think this is a poor testing pattern.
        flags = ['one', 'two', 'three', 'four']
        assert flags_checksum(flags) == 3011366051


class test_get_tool(object):

    def test_without_flag(self):
        assert get_tool('gfortran') == ('gfortran', [])

    def test_with_flag(self):
        assert get_tool('gfortran -c') == ('gfortran', ['-c'])


class Test_get_compiler_version(object):

    def _check(self, full_version_string, expect):
        with mock.patch('fab.tools.run_command', return_value=full_version_string):
            result = get_compiler_version(None)
        assert result == expect

    def test_command_failure(self):
        # if the command fails, we must return an empty string, not None, so it can still be hashed
        with mock.patch('fab.tools.run_command', side_effect=RuntimeError()):
            assert get_compiler_version(None) == '', 'expected empty string'

    def test_unknown_command_response(self):
        # if the full version output is in an unknown format, we must return an empty string
        self._check(full_version_string='foo fortran 1.2.3', expect='')

    def test_unknown_version_format(self):
        # if the version is in an unknown format, we must return an empty string
        full_version_string = dedent("""
            Foo Fortran (Foo) 5 123456 (Foo Hat 4.8.5-44)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        self._check(full_version_string=full_version_string, expect='')

    def test_2_part_version(self):
        # test major.minor format
        full_version_string = dedent("""
            Foo Fortran (Foo) 5.6 123456 (Foo Hat 4.8.5-44)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        self._check(full_version_string=full_version_string, expect='5.6')

    # Possibly overkill to cover so many gfortran versions but I had to go check them so might as well add them.
    # Note: different sources, e.g conda, change the output slightly...

    def test_gfortran_4(self):
        full_version_string = dedent("""
            GNU Fortran (GCC) 4.8.5 20150623 (Red Hat 4.8.5-44)
            Copyright (C) 2015 Free Software Foundation, Inc.

            GNU Fortran comes with NO WARRANTY, to the extent permitted by law.
            You may redistribute copies of GNU Fortran
            under the terms of the GNU General Public License.
            For more information about these matters, see the file named COPYING

        """)

        self._check(full_version_string=full_version_string, expect='4.8.5')

    def test_gfortran_6(self):
        full_version_string = dedent("""
            GNU Fortran (GCC) 6.1.0
            Copyright (C) 2016 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expect='6.1.0')

    def test_gfortran_8(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 8.5.0-16) 8.5.0
            Copyright (C) 2018 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expect='8.5.0')

    def test_gfortran_10(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 10.4.0-16) 10.4.0
            Copyright (C) 2020 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expect='10.4.0')

    def test_gfortran_12(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 12.1.0-16) 12.1.0
            Copyright (C) 2022 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expect='12.1.0')

    def test_ifort_14(self):
        full_version_string = dedent("""
            ifort (IFORT) 14.0.3 20140422
            Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expect='14.0.3')

    def test_ifort_15(self):
        full_version_string = dedent("""
            ifort (IFORT) 15.0.2 20150121
            Copyright (C) 1985-2015 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expect='15.0.2')

    def test_ifort_17(self):
        full_version_string = dedent("""
            ifort (IFORT) 17.0.7 20180403
            Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expect='17.0.7')

    def test_ifort_19(self):
        full_version_string = dedent("""
            ifort (IFORT) 19.0.0.117 20180804
            Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expect='19.0.0.117')


class Test_run_command(object):

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

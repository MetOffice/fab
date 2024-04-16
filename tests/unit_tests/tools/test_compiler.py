##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

from pathlib import Path, PosixPath
from textwrap import dedent
from unittest import mock

import pytest

from fab.newtools import Categories, Compiler, Gcc, Gfortran, Icc, Ifort


def test_compiler():
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER)
    fc.get_version = mock.Mock(return_value="123")
    assert fc.get_version() == "123"


def test_compiler_syntax_only():
    '''Tests handling of syntax only flags.'''
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER)
    assert not fc.has_syntax_only
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                  syntax_only_flag=None)
    assert not fc.has_syntax_only

    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                  syntax_only_flag="-fsyntax-only")
    assert fc.has_syntax_only
    assert fc._syntax_only_flag == "-fsyntax-only"
    fc.run = mock.MagicMock()
    fc.compile_file(Path("a.f90"), "a.o", syntax_only=True)
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['a.f90', '-c', '-o',
                                                     'a.o', '-fsyntax-only'])


def test_compiler_module_output():
    '''Tests handling of module output_flags.'''
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                  module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    fc.compile_file(Path("a.f90"), "a.o", syntax_only=True)
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['a.f90', '-c', '-o',
                                                     'a.o',
                                                     '-J', '/module_out'])


def test_managed_flags():
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                  module_folder_flag="-J")
    for flags, expected in [(["a", "b"], ["a", "b"]),
                            (["-J", "b"], []),
                            (["-Jb"], []),
                            (["a", "-J", "c"], ["a"]),
                            (["a", "-Jc"], ["a"]),
                            (["a", "-J"], ["a", "-J"]),
                            ]:
        fc._remove_managed_flags(flags)
        assert flags == expected


def test_compile_with_add_args():
    fc = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER,
                  module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    fc.compile_file(Path("a.f90"), "a.o", add_flags=["-J/b", "-O3"],
                    syntax_only=True)
    # Notice that "-J/b" has been removed
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['a.f90', '-c', '-o',
                                                     'a.o', "-O3",
                                                     '-J', '/module_out'])


class TestGetCompilerVersion:
    '''Test `get_version`.'''

    def _check(self, full_version_string: str, expected: str):
        '''Checks if the correct version is extracted from the
        given full_version_string.
        '''
        c = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER)
        c.run = mock.Mock(return_value=full_version_string)
        assert c.get_version() == expected
        # Now let the run method raise an exception, to make sure
        # we now get a cached value back:
        c.run = mock.Mock(side_effect=RuntimeError(""))
        assert c.get_version() == expected

    def test_command_failure(self):
        # if the command fails, we must return an empty string,
        # not None, so it can still be hashed
        c = Compiler("gfortran", "gfortran", Categories.FORTRAN_COMPILER)
        c.run = mock.Mock()
        with mock.patch.object(c, 'run', side_effect=RuntimeError()):
            assert c.get_version() == '', 'expected empty string'
        with mock.patch.object(c, 'run', side_effect=FileNotFoundError()):
            with pytest.raises(ValueError) as err:
                c.get_version()
            assert "Compiler not found: gfortran" in str(err.value)

    def test_unknown_command_response(self):
        '''If the full version output is in an unknown format,
        we must return an empty string.'''
        self._check(full_version_string='foo fortran 1.2.3', expected='')

    def test_unknown_version_format(self):
        '''If the version is in an unknown format, we must return an
        empty string.'''
        full_version_string = dedent("""
            Foo Fortran (Foo) 5 123456 (Foo Hat 4.8.5-44)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        self._check(full_version_string=full_version_string, expected='')

    def test_2_part_version(self):
        '''Test major.minor format. '''
        full_version_string = dedent("""
            Foo Fortran (Foo) 5.6 123456 (Foo Hat 4.8.5-44)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        self._check(full_version_string=full_version_string, expected='5.6')

    # Possibly overkill to cover so many gfortran versions but I had to go
    # check them so might as well add them.
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

        self._check(full_version_string=full_version_string, expected='4.8.5')

    def test_gfortran_6(self):
        full_version_string = dedent("""
            GNU Fortran (GCC) 6.1.0
            Copyright (C) 2016 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='6.1.0')

    def test_gfortran_8(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 8.5.0-16) 8.5.0
            Copyright (C) 2018 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='8.5.0')

    def test_gfortran_10(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 10.4.0-16) 10.4.0
            Copyright (C) 2020 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='10.4.0')

    def test_gfortran_12(self):
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 12.1.0-16) 12.1.0
            Copyright (C) 2022 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='12.1.0')

    def test_ifort_14(self):
        full_version_string = dedent("""
            ifort (IFORT) 14.0.3 20140422
            Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='14.0.3')

    def test_ifort_15(self):
        full_version_string = dedent("""
            ifort (IFORT) 15.0.2 20150121
            Copyright (C) 1985-2015 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='15.0.2')

    def test_ifort_17(self):
        full_version_string = dedent("""
            ifort (IFORT) 17.0.7 20180403
            Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='17.0.7')

    def test_ifort_19(self):
        full_version_string = dedent("""
            ifort (IFORT) 19.0.0.117 20180804
            Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string,
                    expected='19.0.0.117')


def test_gcc():
    '''Tests the gcc class.'''
    gcc = Gcc()
    assert gcc.name == "gcc"
    assert gcc.category == Categories.C_COMPILER


def test_gfortran():
    '''Tests the gfortran class.'''
    gfortran = Gfortran()
    assert gfortran.name == "gfortran"
    assert gfortran.category == Categories.FORTRAN_COMPILER


def test_icc():
    '''Tests the icc class.'''
    icc = Icc()
    assert icc.name == "icc"
    assert icc.category == Categories.C_COMPILER


def test_ifort():
    '''Tests the ifort class.'''
    ifort = Ifort()
    assert ifort.name == "ifort"
    assert ifort.category == Categories.FORTRAN_COMPILER

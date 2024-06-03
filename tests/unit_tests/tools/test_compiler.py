##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################

'''Tests the compiler implementation.
'''

import os
from pathlib import Path, PosixPath
from textwrap import dedent
from unittest import mock

import pytest

from fab.tools import (Categories, CCompiler, Compiler, FortranCompiler,
                       Gcc, Gfortran, Icc, Ifort)


def test_compiler():
    '''Test the compiler constructor.'''
    cc = CCompiler("gcc", "gcc", "gnu")
    assert cc.category == Categories.C_COMPILER
    assert cc._compile_flag == "-c"
    assert cc._output_flag == "-o"
    assert cc.flags == []
    assert cc.vendor == "gnu"

    fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J")
    assert fc._compile_flag == "-c"
    assert fc._output_flag == "-o"
    assert fc.category == Categories.FORTRAN_COMPILER
    assert fc.vendor == "gnu"
    assert fc.flags == []


def test_compiler_check_available():
    '''Check if check_available works as expected. The compiler class
    uses internally get_version to test if a compiler works or not.
    '''
    cc = CCompiler("gcc", "gcc", "gnu")
    # The compiler uses get_version to check if it is available.
    # First simulate a successful run:
    with mock.patch.object(cc, "get_version", returncode=123):
        assert cc.check_available()

    # Now test if get_version raises an error
    with mock.patch.object(cc, "get_version", side_effect=RuntimeError("")):
        assert not cc.check_available()


def test_compiler_hash():
    '''Test the hash functionality.'''
    cc = CCompiler("gcc", "gcc", "gnu")
    with mock.patch.object(cc, "_version", 567):
        hash1 = cc.get_hash()
        assert hash1 == 4646426180

    # A change in the version number must change the hash:
    with mock.patch.object(cc, "_version", 89):
        hash2 = cc.get_hash()
        assert hash2 != hash1

    # A change in the name must change the hash, again:
    cc._name = "new_name"
    hash3 = cc.get_hash()
    assert hash3 not in (hash1, hash2)


def test_compiler_with_env_fflags():
    '''Test that content of FFLAGS is added to the compiler flags.'''
    with mock.patch.dict(os.environ, FFLAGS='--foo --bar'):
        cc = CCompiler("gcc", "gcc", "gnu")
        fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J")
    assert cc.flags == ["--foo", "--bar"]
    assert fc.flags == ["--foo", "--bar"]


def test_compiler_syntax_only():
    '''Tests handling of syntax only flags.'''
    fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J")
    assert not fc.has_syntax_only
    fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J",
                         syntax_only_flag=None)
    assert not fc.has_syntax_only

    fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J",
                         syntax_only_flag="-fsyntax-only")
    fc.set_module_output_path("/tmp")
    assert fc.has_syntax_only
    assert fc._syntax_only_flag == "-fsyntax-only"
    fc.run = mock.Mock()
    fc.compile_file(Path("a.f90"), "a.o", syntax_only=True)
    fc.run.assert_called_with(cwd=Path('.'),
                              additional_parameters=['-c', '-fsyntax-only',
                                                     "-J", '/tmp', 'a.f90',
                                                     '-o', 'a.o', ])


def test_compiler_module_output():
    '''Tests handling of module output_flags.'''
    fc = FortranCompiler("gfortran", "gfortran", vendor="gnu",
                         module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    fc.compile_file(Path("a.f90"), "a.o", syntax_only=True)
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['-c', '-J', '/module_out',
                                                     'a.f90', '-o', 'a.o'])


def test_compiler_with_add_args():
    '''Tests that additional arguments are handled as expected.'''
    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    with pytest.warns(UserWarning, match="Removing managed flag"):
        fc.compile_file(Path("a.f90"), "a.o", add_flags=["-J/b", "-O3"],
                        syntax_only=True)
    # Notice that "-J/b" has been removed
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['-c', "-O3",
                                                     '-J', '/module_out',
                                                     'a.f90', '-o', 'a.o'])


class TestGetCompilerVersion:
    '''Test `get_version`.'''

    def _check(self, full_version_string: str, expected: str):
        '''Checks if the correct version is extracted from the
        given full_version_string.
        '''
        c = Compiler("gfortran", "gfortran", "gnu",
                     Categories.FORTRAN_COMPILER)
        with mock.patch.object(c, "run",
                               mock.Mock(return_value=full_version_string)):
            assert c.get_version() == expected
        # Now let the run method raise an exception, to make sure
        # we get a cached value back (and the run method isn't called again):
        with mock.patch.object(c, "run",
                               mock.Mock(side_effect=RuntimeError(""))):
            assert c.get_version() == expected

    def test_command_failure(self):
        '''If the command fails, we must return an empty string, not None,
        so it can still be hashed.'''
        c = Compiler("gfortran", "gfortran", "gnu",
                     Categories.FORTRAN_COMPILER)
        with mock.patch.object(c, 'run', side_effect=RuntimeError()):
            assert c.get_version() == '', 'expected empty string'
        with mock.patch.object(c, 'run', side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError) as err:
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
        '''Test gfortran 4.8.5 version detection.'''
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
        '''Test gfortran 6.1.0 version detection.'''
        full_version_string = dedent("""
            GNU Fortran (GCC) 6.1.0
            Copyright (C) 2016 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='6.1.0')

    def test_gfortran_8(self):
        '''Test gfortran 8.5.0 version detection.'''
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 8.5.0-16) 8.5.0
            Copyright (C) 2018 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='8.5.0')

    def test_gfortran_10(self):
        '''Test gfortran 10.4.0 version detection.'''
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 10.4.0-16) 10.4.0
            Copyright (C) 2020 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='10.4.0')

    def test_gfortran_12(self):
        '''Test gfortran 12.1.0 version detection.'''
        full_version_string = dedent("""
            GNU Fortran (conda-forge gcc 12.1.0-16) 12.1.0
            Copyright (C) 2022 Free Software Foundation, Inc.
            This is free software; see the source for copying conditions.  There is NO
            warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

        """)

        self._check(full_version_string=full_version_string, expected='12.1.0')

    def test_ifort_14(self):
        '''Test ifort 14.0.3 version detection.'''
        full_version_string = dedent("""
            ifort (IFORT) 14.0.3 20140422
            Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='14.0.3')

    def test_ifort_15(self):
        '''Test ifort 15.0.2 version detection.'''
        full_version_string = dedent("""
            ifort (IFORT) 15.0.2 20150121
            Copyright (C) 1985-2015 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='15.0.2')

    def test_ifort_17(self):
        '''Test ifort 17.0.7 version detection.'''
        full_version_string = dedent("""
            ifort (IFORT) 17.0.7 20180403
            Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

        """)

        self._check(full_version_string=full_version_string, expected='17.0.7')

    def test_ifort_19(self):
        '''Test ifort 19.0.0.117 version detection.'''
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
    assert isinstance(gcc, CCompiler)
    assert gcc.category == Categories.C_COMPILER


def test_gfortran():
    '''Tests the gfortran class.'''
    gfortran = Gfortran()
    assert gfortran.name == "gfortran"
    assert isinstance(gfortran, FortranCompiler)
    assert gfortran.category == Categories.FORTRAN_COMPILER


def test_icc():
    '''Tests the icc class.'''
    icc = Icc()
    assert icc.name == "icc"
    assert isinstance(icc, CCompiler)
    assert icc.category == Categories.C_COMPILER


def test_ifort():
    '''Tests the ifort class.'''
    ifort = Ifort()
    assert ifort.name == "ifort"
    assert isinstance(ifort, FortranCompiler)
    assert ifort.category == Categories.FORTRAN_COMPILER


def test_compiler_wrapper():
    '''Make sure we can easily create a compiler wrapper.'''
    class MpiF90(Ifort):
        '''A simple compiler wrapper'''
        def __init__(self):
            super().__init__(name="mpif90-intel",
                             exec_name="mpif90")

    mpif90 = MpiF90()
    assert mpif90.vendor == "intel"
    assert mpif90.category == Categories.FORTRAN_COMPILER
    assert mpif90.name == "mpif90-intel"
    assert mpif90.exec_name == "mpif90"

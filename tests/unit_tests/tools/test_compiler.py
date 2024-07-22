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

from fab.tools import (Category, CCompiler, Compiler, FortranCompiler,
                       Gcc, Gfortran, Icc, Ifort)


def test_compiler():
    '''Test the compiler constructor.'''
    cc = CCompiler("gcc", "gcc", "gnu")
    assert cc.category == Category.C_COMPILER
    assert cc._compile_flag == "-c"
    assert cc._output_flag == "-o"
    assert cc.flags == []
    assert cc.suite == "gnu"

    fc = FortranCompiler("gfortran", "gfortran", "gnu", "-J")
    assert fc._compile_flag == "-c"
    assert fc._output_flag == "-o"
    assert fc.category == Category.FORTRAN_COMPILER
    assert fc.suite == "gnu"
    assert fc.flags == []


def test_available():
    '''Check if check_available works as expected. The compiler class uses
    internally get_version to test if a compiler works or not. Check the
    compiler is available when it has a valid version.
    '''
    cc = CCompiler("gcc", "gcc", "gnu")
    with mock.patch.object(cc, "get_version", returncode=(1, 2, 3)):
        assert cc.check_available()


def test_available_after_error():
    ''' Check the compiler is not available when get_version raises an error.
    '''
    cc = CCompiler("gcc", "gcc", "gnu")
    with mock.patch.object(cc, "get_version", side_effect=RuntimeError("")):
        assert not cc.check_available()


def test_compiler_hash():
    '''Test the hash functionality.'''
    cc = CCompiler("gcc", "gcc", "gnu")
    with mock.patch.object(cc, "_version", (5, 6, 7)):
        hash1 = cc.get_hash()
        assert hash1 == 2768517656

    # A change in the version number must change the hash:
    with mock.patch.object(cc, "_version", (8, 9)):
        hash2 = cc.get_hash()
        assert hash2 != hash1

        # A change in the name must change the hash, again:
        cc._name = "new_name"
        hash3 = cc.get_hash()
        assert hash3 not in (hash1, hash2)


def test_compiler_hash_compiler_error():
    '''Test the hash functionality when version info is missing.'''
    cc = CCompiler("gcc", "gcc", "gnu")

    # raise an error when trying to get compiler version
    with mock.patch.object(cc, 'run', side_effect=RuntimeError()):
        with pytest.raises(RuntimeError):
            cc.get_hash()


def test_compiler_hash_invalid_version():
    '''Test the hash functionality when version info is missing.'''
    cc = CCompiler("gcc", "gcc", "gnu")

    # returns an invalid compiler version string
    with mock.patch.object(cc, "run", mock.Mock(return_value='foo v1')):
        with pytest.raises(RuntimeError):
            cc.get_hash()


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
    fc = FortranCompiler("gfortran", "gfortran", suite="gnu",
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

    def _check_error(self, full_version_string: str, expected_error: str):
        '''Checks if the correct error is raised from the given invalid
        full_version_string.
        '''
        c = Compiler("Foo Fortran", "footran", "gnu", Category.FORTRAN_COMPILER)
        with mock.patch.object(c, "run",
                               mock.Mock(return_value=full_version_string)):
            with pytest.raises(RuntimeError) as err:
                c.get_version()
            assert expected_error in str(err.value)

    def _check(self, full_version_string: str, expected: str):
        '''Checks if the correct version is extracted from the given
        full_version_string.
        '''
        c = Compiler("Foo Fortran", "footran", "gnu", Category.FORTRAN_COMPILER)
        with mock.patch.object(c, "run",
                               mock.Mock(return_value=full_version_string)):
            assert c.get_version() == expected
        # Now let the run method raise an exception, to make sure
        # we get a cached value back (and the run method isn't called again):
        with mock.patch.object(c, "run",
                               mock.Mock(side_effect=RuntimeError(""))):
            assert c.get_version() == expected

    def test_command_failure(self):
        '''If the version command fails, we must raise an error.'''
        c = Compiler("Foo Fortran", "footran", "gnu",
                     Category.FORTRAN_COMPILER)
        with mock.patch.object(c, 'run', side_effect=RuntimeError()):
            with pytest.raises(RuntimeError) as err:
                c.get_version()
            assert "Error asking for version of compiler" in str(err.value)

    def test_file_not_found(self):
        '''If the compiler is not found, we must raise an error.'''
        c = Compiler("Foo Fortran", "footran", "gnu",
                     Category.FORTRAN_COMPILER)
        with mock.patch.object(c, 'run', side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError) as err:
                c.get_version()
            assert "Compiler not found: Foo Fortran" in str(err.value)

    def test_unknown_command_response(self):
        '''If the full version output is in an unknown format,
        we must raise an error.'''
        full_version_string = 'Foo Fortran 1.2.3'
        expected_error = "Unexpected version response from compiler 'Foo Fortran'"
        self._check_error(
            full_version_string=full_version_string,
            expected_error=expected_error
        )

    def test_unknown_version_format(self):
        '''If the version is in an unknown format, we must raise an error.'''

        full_version_string = dedent("""
            Foo Fortran (Foo) 5 123456 (Foo Hat 4.8.5-44)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        expected_error = "Unexpected compiler version format for compiler 'Foo Fortran'"
        self._check_error(
            full_version_string=full_version_string,
            expected_error=expected_error
        )

    def test_non_int_version_format(self):
        '''If the version contains non-number characters, we must raise an error.'''
        full_version_string = dedent("""
            Foo Fortran (Foo) 5.1f.2g (Foo Hat 4.8.5)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        expected_error = "Unexpected compiler version format for compiler 'Foo Fortran'"
        self._check_error(
            full_version_string=full_version_string,
            expected_error=expected_error
        )

    def test_1_part_version(self):
        '''If the version is just one integer, that is invalid and we must
        raise an error. '''
        full_version_string = dedent("""
            Foo Fortran (Foo) 77
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        expected_error = "Unexpected compiler version format for compiler 'Foo Fortran'"
        self._check_error(
            full_version_string=full_version_string,
            expected_error=expected_error
        )

    def test_2_part_version(self):
        '''Test major.minor format. '''
        full_version_string = dedent("""
            Foo Fortran (Foo) 5.6 123456 (Foo Hat 1.2.3-45)
            Copyright (C) 2022 Foo Software Foundation, Inc.
        """)
        self._check(full_version_string=full_version_string, expected=(5, 6))

    def test_3_part_version(self):
        '''Test major.minor.patch format. '''
        full_version_string = dedent("""
            Foo Fortran (Foo) 6.1.0
        """)
        self._check(full_version_string=full_version_string, expected=(6, 1, 0))

    def test_4_part_version(self):
        '''Test major.minor.patch.revision format. '''
        full_version_string = dedent("""
            Foo Fortran (Foo) 19.0.0.117 20180804
        """)
        self._check(full_version_string=full_version_string, expected=(19, 0, 0, 117))


# ============================================================================
def test_gcc():
    '''Tests the gcc class.'''
    gcc = Gcc()
    assert gcc.name == "gcc"
    assert isinstance(gcc, CCompiler)
    assert gcc.category == Category.C_COMPILER


def test_gcc_get_version():
    '''Tests the gcc class.'''
    gcc = Gcc()
    full_version_string = dedent("""
        gcc (GCC) 8.5.0 20210514 (Red Hat 8.5.0-20)
        Copyright (C) 2018 Free Software Foundation, Inc.
    """)
    with mock.patch.object(gcc, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gcc.get_version() == (8, 5, 0)


def test_gcc_get_version_with_icc_string():
    '''Tests the gcc class.'''
    gcc = Gcc()
    full_version_string = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    with mock.patch.object(gcc, "run",
                           mock.Mock(return_value=full_version_string)):
        with pytest.raises(RuntimeError) as err:
            gcc.get_version()
        assert "Unexpected version for gcc compiler" in str(err.value)


# ============================================================================
def test_gfortran():
    '''Tests the gfortran class.'''
    gfortran = Gfortran()
    assert gfortran.name == "gfortran"
    assert isinstance(gfortran, FortranCompiler)
    assert gfortran.category == Category.FORTRAN_COMPILER


# Possibly overkill to cover so many gfortran versions but I had to go
# check them so might as well add them.
# Note: different sources, e.g conda, change the output slightly...


def test_gfortran_get_version_4():
    '''Test gfortran 4.8.5 version detection.'''
    full_version_string = dedent("""
        GNU Fortran (GCC) 4.8.5 20150623 (Red Hat 4.8.5-44)
        Copyright (C) 2015 Free Software Foundation, Inc.

        GNU Fortran comes with NO WARRANTY, to the extent permitted by law.
        You may redistribute copies of GNU Fortran
        under the terms of the GNU General Public License.
        For more information about these matters, see the file named COPYING

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gfortran.get_version() == (4, 8, 5)


def test_gfortran_get_version_6():
    '''Test gfortran 6.1.0 version detection.'''
    full_version_string = dedent("""
        GNU Fortran (GCC) 6.1.0
        Copyright (C) 2016 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gfortran.get_version() == (6, 1, 0)


def test_gfortran_get_version_8():
    '''Test gfortran 8.5.0 version detection.'''
    full_version_string = dedent("""
        GNU Fortran (conda-forge gcc 8.5.0-16) 8.5.0
        Copyright (C) 2018 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gfortran.get_version() == (8, 5, 0)


def test_gfortran_get_version_10():
    '''Test gfortran 10.4.0 version detection.'''
    full_version_string = dedent("""
        GNU Fortran (conda-forge gcc 10.4.0-16) 10.4.0
        Copyright (C) 2020 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gfortran.get_version() == (10, 4, 0)


def test_gfortran_get_version_12():
    '''Test gfortran 12.1.0 version detection.'''
    full_version_string = dedent("""
        GNU Fortran (conda-forge gcc 12.1.0-16) 12.1.0
        Copyright (C) 2022 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        assert gfortran.get_version() == (12, 1, 0)


def test_gfortran_get_version_with_ifort_string():
    '''Tests the gfortran class with an ifort version string.'''
    full_version_string = dedent("""
        ifort (IFORT) 14.0.3 20140422
        Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_version_string)):
        with pytest.raises(RuntimeError) as err:
            gfortran.get_version()
        assert "Unexpected version for gfortran compiler" in str(err.value)


# ============================================================================
def test_icc():
    '''Tests the icc class.'''
    icc = Icc()
    assert icc.name == "icc"
    assert isinstance(icc, CCompiler)
    assert icc.category == Category.C_COMPILER


def test_icc_get_version():
    '''Tests the icc class get_version method.'''
    full_version_string = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    icc = Icc()
    with mock.patch.object(icc, "run",
                           mock.Mock(return_value=full_version_string)):
        assert icc.get_version() == (2021, 10, 0)


def test_icc_get_version_with_gcc_string():
    '''Tests the icc class with a GCC version string.'''
    full_version_string = dedent("""
        gcc (GCC) 8.5.0 20210514 (Red Hat 8.5.0-20)
        Copyright (C) 2018 Free Software Foundation, Inc.
    """)
    icc = Icc()
    with mock.patch.object(icc, "run",
                           mock.Mock(return_value=full_version_string)):
        with pytest.raises(RuntimeError) as err:
            icc.get_version()
        assert "Unexpected version for icc compiler" in str(err.value)


# ============================================================================
def test_ifort():
    '''Tests the ifort class.'''
    ifort = Ifort()
    assert ifort.name == "ifort"
    assert isinstance(ifort, FortranCompiler)
    assert ifort.category == Category.FORTRAN_COMPILER


def test_ifort_get_version_14():
    '''Test ifort 14.0.3 version detection.'''
    full_version_string = dedent("""
        ifort (IFORT) 14.0.3 20140422
        Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run",
                           mock.Mock(return_value=full_version_string)):
        assert ifort.get_version() == (14, 0, 3)

def test_ifort_get_version_15():
    '''Test ifort 15.0.2 version detection.'''
    full_version_string = dedent("""
        ifort (IFORT) 15.0.2 20150121
        Copyright (C) 1985-2015 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run",
                           mock.Mock(return_value=full_version_string)):
        assert ifort.get_version() == (15, 0, 2)

def test_ifort_get_version_17():
    '''Test ifort 17.0.7 version detection.'''
    full_version_string = dedent("""
        ifort (IFORT) 17.0.7 20180403
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run",
                           mock.Mock(return_value=full_version_string)):
        assert ifort.get_version() == (17, 0, 7)

def test_ifort_get_version_19():
    '''Test ifort 19.0.0.117 version detection.'''
    full_version_string = dedent("""
        ifort (IFORT) 19.0.0.117 20180804
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run",
                           mock.Mock(return_value=full_version_string)):
        assert ifort.get_version() == (19, 0, 0, 117)


def test_ifort_get_version_with_icc_string():
    '''Tests the icc class.'''
    full_version_string = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run",
                           mock.Mock(return_value=full_version_string)):
        with pytest.raises(RuntimeError) as err:
            ifort.get_version()
        assert "Unexpected version for ifort compiler" in str(err.value)


# ============================================================================
def test_compiler_wrapper():
    '''Make sure we can easily create a compiler wrapper.'''
    class MpiF90(Ifort):
        '''A simple compiler wrapper'''
        def __init__(self):
            super().__init__(name="mpif90-intel",
                             exec_name="mpif90")

    mpif90 = MpiF90()
    assert mpif90.suite == "intel-classic"
    assert mpif90.category == Category.FORTRAN_COMPILER
    assert mpif90.name == "mpif90-intel"
    assert mpif90.exec_name == "mpif90"

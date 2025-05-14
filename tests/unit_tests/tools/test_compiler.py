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

from fab.tools import (Category, CCompiler, Compiler, Craycc, Crayftn,
                       FortranCompiler, Gcc, Gfortran, Icc, Icx, Ifort, Ifx,
                       Nvc, Nvfortran)


def test_compiler():
    '''Test the compiler constructor.'''
    cc = Compiler("gcc", "gcc", "gnu", version_regex="some_regex",
                  category=Category.C_COMPILER, openmp_flag="-fopenmp")
    assert cc.category == Category.C_COMPILER
    assert cc._compile_flag == "-c"
    assert cc._output_flag == "-o"
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert cc.flags == []
    assert cc.suite == "gnu"
    assert not cc.mpi
    assert cc.openmp_flag == "-fopenmp"

    fc = FortranCompiler("gfortran", "gfortran", "gnu", openmp_flag="-fopenmp",
                         version_regex="something", module_folder_flag="-J")
    assert fc._compile_flag == "-c"
    assert fc._output_flag == "-o"
    assert fc.category == Category.FORTRAN_COMPILER
    assert fc.suite == "gnu"
    # pylint: disable-next=use-implicit-booleaness-not-comparison
    assert fc.flags == []
    assert not fc.mpi
    assert fc.openmp_flag == "-fopenmp"


def test_compiler_openmp():
    '''Test that the openmp flag is correctly reflected in the test if
    a compiler supports OpenMP or not.'''
    cc = CCompiler("gcc", "gcc", "gnu", openmp_flag="-fopenmp",
                   version_regex=None)
    assert cc.openmp_flag == "-fopenmp"
    assert cc.openmp
    cc = CCompiler("gcc", "gcc", "gnu", openmp_flag=None, version_regex=None)
    assert cc.openmp_flag == ""
    assert not cc.openmp
    cc = CCompiler("gcc", "gcc", "gnu", version_regex=None)
    assert cc.openmp_flag == ""
    assert not cc.openmp

    fc = FortranCompiler("gfortran", "gfortran", "gnu", openmp_flag="-fopenmp",
                         module_folder_flag="-J", version_regex=None)
    assert fc.openmp_flag == "-fopenmp"
    assert fc.openmp
    fc = FortranCompiler("gfortran", "gfortran", "gnu", openmp_flag=None,
                         module_folder_flag="-J", version_regex=None)
    assert fc.openmp_flag == ""
    assert not fc.openmp
    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         module_folder_flag="-J", version_regex=None)
    assert fc.openmp_flag == ""
    assert not fc.openmp


def test_compiler_check_available():
    '''Check if check_available works as expected. The compiler class uses
    internally get_version to test if a compiler works or not. Check the
    compiler is available when it has a valid version.
    '''
    cc = Gcc()
    with mock.patch.object(cc, "get_version", returncode=(1, 2, 3)):
        assert cc.check_available()


def test_compiler_check_available_runtime_error():
    ''' Check the compiler is not available when get_version raises an error.
    '''
    cc = Gcc()
    with mock.patch.object(cc, "get_version", side_effect=RuntimeError("")):
        assert not cc.check_available()


def test_compiler_hash():
    '''Test the hash functionality.'''
    cc = Gcc()
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
    cc = Gcc()

    # raise an error when trying to get compiler version
    with mock.patch.object(cc, 'run', side_effect=RuntimeError()):
        with pytest.raises(RuntimeError) as err:
            cc.get_hash()
        assert "Error asking for version of compiler" in str(err.value)


def test_compiler_hash_invalid_version():
    '''Test the hash functionality when version info is missing.'''
    cc = Gcc()

    # returns an invalid compiler version string
    with mock.patch.object(cc, "run", mock.Mock(return_value='foo v1')):
        with pytest.raises(RuntimeError) as err:
            cc.get_hash()
        assert ("Unexpected version output format for compiler 'gcc'"
                in str(err.value))


def test_compiler_with_env_fflags():
    '''Test that content of FFLAGS is added to the compiler flags.'''
    with mock.patch.dict(os.environ, FFLAGS='--foo --bar'):
        cc = Gcc()
        fc = Gfortran()
    assert cc.flags == ["--foo", "--bar"]
    assert fc.flags == ["--foo", "--bar"]


def test_compiler_syntax_only():
    '''Tests handling of syntax only flags.'''
    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         version_regex="something",
                         openmp_flag="-fopenmp", module_folder_flag="-J")
    # Empty since no flag is defined
    assert not fc.has_syntax_only

    fc = FortranCompiler("gfortran", "gfortran", "gnu", openmp_flag="-fopenmp",
                         version_regex="something", module_folder_flag="-J",
                         syntax_only_flag=None)
    # Empty since no flag is defined
    assert not fc.has_syntax_only

    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         version_regex="something",
                         openmp_flag="-fopenmp",
                         module_folder_flag="-J",
                         syntax_only_flag="-fsyntax-only")
    assert fc.has_syntax_only
    assert fc._syntax_only_flag == "-fsyntax-only"


def test_compiler_without_openmp():
    '''Tests that the openmp flag is not used when openmp is not enabled. '''
    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         version_regex="something",
                         openmp_flag="-fopenmp",
                         module_folder_flag="-J",
                         syntax_only_flag="-fsyntax-only")
    fc.set_module_output_path("/tmp")
    fc.run = mock.Mock()
    fc.compile_file(Path("a.f90"), "a.o", openmp=False, syntax_only=True)
    fc.run.assert_called_with(cwd=Path('.'),
                              additional_parameters=['-c', '-fsyntax-only',
                                                     "-J", '/tmp', 'a.f90',
                                                     '-o', 'a.o', ])


def test_compiler_with_openmp():
    '''Tests that the openmp flag is used as expected if openmp is enabled.
    '''
    fc = FortranCompiler("gfortran", "gfortran", "gnu",
                         version_regex="something",
                         openmp_flag="-fopenmp",
                         module_folder_flag="-J",
                         syntax_only_flag="-fsyntax-only")
    fc.set_module_output_path("/tmp")
    fc.run = mock.Mock()
    fc.compile_file(Path("a.f90"), "a.o", openmp=True, syntax_only=False)
    fc.run.assert_called_with(cwd=Path('.'),
                              additional_parameters=['-c', '-fopenmp',
                                                     "-J", '/tmp', 'a.f90',
                                                     '-o', 'a.o', ])


def test_compiler_module_output():
    '''Tests handling of module output_flags.'''
    fc = FortranCompiler("gfortran", "gfortran", suite="gnu",
                         version_regex="something", module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    fc.compile_file(Path("a.f90"), "a.o", openmp=False, syntax_only=True)
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['-c', '-J', '/module_out',
                                                     'a.f90', '-o', 'a.o'])


def test_compiler_with_add_args():
    '''Tests that additional arguments are handled as expected.'''
    fc = FortranCompiler("gfortran", "gfortran", suite="gnu",
                         version_regex="something",
                         openmp_flag="-fopenmp",
                         module_folder_flag="-J")
    fc.set_module_output_path("/module_out")
    assert fc._module_output_path == "/module_out"
    fc.run = mock.MagicMock()
    with pytest.warns(UserWarning, match="Removing managed flag"):
        fc.compile_file(Path("a.f90"), "a.o", add_flags=["-J/b", "-O3"],
                        openmp=False, syntax_only=True)
    # Notice that "-J/b" has been removed
    fc.run.assert_called_with(cwd=PosixPath('.'),
                              additional_parameters=['-c', "-O3",
                                                     '-J', '/module_out',
                                                     'a.f90', '-o', 'a.o'])
    with pytest.warns(UserWarning,
                      match="explicitly provided. OpenMP should be enabled in "
                            "the BuildConfiguration"):
        fc.compile_file(Path("a.f90"), "a.o",
                        add_flags=["-fopenmp", "-O3"],
                        openmp=True, syntax_only=True)


# ============================================================================
# Test version number handling
# ============================================================================
def test_get_version_string():
    '''Tests the get_version_string() method.
    '''
    full_output = 'GNU Fortran (gcc) 6.1.0'

    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        assert c.get_version_string() == "6.1.0"


def test_get_version_1_part_version():
    '''
    Tests the get_version() method with an invalid format.
    If the version is just one integer, that is invalid and we must raise an
    error. '''
    full_output = dedent("""
        GNU Fortran (gcc) 777
        Copyright (C) 2022 Foo Software Foundation, Inc.
    """)
    expected_error = "Unexpected version output format for compiler"

    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            c.get_version()
        assert expected_error in str(err.value)


def test_get_version_2_part_version():
    '''
    Tests the get_version() method with a valid format.
    Test major.minor format.
    '''
    full_output = dedent("""
        GNU Fortran (gcc) 5.6 123456 (Foo Hat 1.2.3-45)
        Copyright (C) 2022 Foo Software Foundation, Inc.
    """)
    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        assert c.get_version() == (5, 6)


def test_get_version_3_part_version():
    '''
    Tests the get_version() method with a valid format.
    Test major.minor.patch format.
    '''
    full_output = 'GNU Fortran (gcc) 6.1.0'
    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        assert c.get_version() == (6, 1, 0)


def test_get_version_4_part_version():
    '''
    Tests the get_version() method with a valid format.
    Test major.minor.patch.revision format.
    '''
    full_output = 'GNU Fortran (gcc) 19.0.0.117 20180804'
    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        assert c.get_version() == (19, 0, 0, 117)


@pytest.mark.parametrize("version", ["5.15f.2",
                                     ".0.5.1",
                                     "0.5.1.",
                                     "0.5..1"])
def test_get_version_non_int_version_format(version):
    '''
    Tests the get_version() method with an invalid format.
    If the version contains non-number characters, we must raise an error.
    TODO: the current code does not detect an error in case of `1.2..`,
    i.e. a trailing ".".
    '''
    full_output = dedent(f"""
        GNU Fortran (gcc) {version} (Foo Hat 4.8.5)
        Copyright (C) 2022 Foo Software Foundation, Inc.
    """)
    expected_error = "Unexpected version output format for compiler"

    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            c.get_version()
        assert expected_error in str(err.value)


def test_get_version_unknown_version_format():
    '''
    Tests the get_version() method with an invalid format.
    If the version is in an unknown format, we must raise an error.
    '''

    full_output = dedent("""
        Foo Fortran version 175
    """)
    expected_error = "Unexpected version output format for compiler"

    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            c.get_version()
        assert expected_error in str(err.value)


def test_get_version_command_failure():
    '''If the version command fails, we must raise an error.'''
    c = Gfortran(exec_name="does_not_exist")
    with pytest.raises(RuntimeError) as err:
        c.get_version()
    assert "Error asking for version of compiler" in str(err.value)


def test_get_version_unknown_command_response():
    '''If the full version output is in an unknown format,
    we must raise an error.'''
    full_output = 'GNU Fortran  1.2.3'
    expected_error = "Unexpected version output format for compiler"

    c = Gfortran()
    with mock.patch.object(c, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            c.get_version()
        assert expected_error in str(err.value)


def test_get_version_good_result_is_cached():
    '''Checks that the compiler is only run once to extract the version.
    '''
    valid_output = "GNU Fortran (gcc) 6.1.0"
    expected = (6, 1, 0)
    c = Gfortran()
    with mock.patch.object(c, 'run', mock.Mock(return_value=valid_output)):
        assert c.get_version() == expected
        assert c.run.called

    # Now let the run method raise an exception, to make sure we get a cached
    # value back (and the run method isn't called again):
    with mock.patch.object(c, 'run', side_effect=RuntimeError()):
        assert c.get_version() == expected
        assert not c.run.called


def test_get_version_bad_result_is_not_cached():
    '''Checks that the compiler can be re-run after failing to get the version.
    '''
    # Set up the compiler to fail the first time
    c = Gfortran()
    with mock.patch.object(c, 'run', side_effect=RuntimeError()):
        with pytest.raises(RuntimeError):
            c.get_version()

    # Now let the run method run successfully and we should get the version.
    valid_output = "GNU Fortran (gcc) 6.1.0"
    with mock.patch.object(c, 'run', mock.Mock(return_value=valid_output)):
        assert c.get_version() == (6, 1, 0)
        assert c.run.called


# ============================================================================
# gcc
# ============================================================================
def test_gcc():
    '''Tests the gcc class.'''
    gcc = Gcc()
    assert gcc.name == "gcc"
    assert isinstance(gcc, CCompiler)
    assert gcc.category == Category.C_COMPILER
    assert not gcc.mpi


def test_gcc_get_version():
    '''Tests the gcc class get_version method.'''
    gcc = Gcc()
    full_output = dedent("""
        gcc (GCC) 8.5.0 20210514 (Red Hat 8.5.0-20)
        Copyright (C) 2018 Free Software Foundation, Inc.
    """)
    with mock.patch.object(gcc, "run", mock.Mock(return_value=full_output)):
        assert gcc.get_version() == (8, 5, 0)


def test_gcc_get_version_with_icc_string():
    '''Tests the gcc class with an icc version output.'''
    gcc = Gcc()
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    with mock.patch.object(gcc, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            gcc.get_version()
        assert "Unexpected version output format for compiler" in str(err.value)


# ============================================================================
# gfortran
# ============================================================================
def test_gfortran():
    '''Tests the gfortran class.'''
    gfortran = Gfortran()
    assert gfortran.name == "gfortran"
    assert isinstance(gfortran, FortranCompiler)
    assert gfortran.category == Category.FORTRAN_COMPILER
    assert not gfortran.mpi


# Possibly overkill to cover so many gfortran versions but I had to go
# check them so might as well add them.
# Note: different sources, e.g conda, change the output slightly...


def test_gfortran_get_version_4():
    '''Test gfortran 4.8.5 version detection.'''
    full_output = dedent("""
        GNU Fortran (GCC) 4.8.5 20150623 (Red Hat 4.8.5-44)
        Copyright (C) 2015 Free Software Foundation, Inc.

        GNU Fortran comes with NO WARRANTY, to the extent permitted by law.
        You may redistribute copies of GNU Fortran
        under the terms of the GNU General Public License.
        For more information about these matters, see the file named COPYING

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run", mock.Mock(return_value=full_output)):
        assert gfortran.get_version() == (4, 8, 5)


def test_gfortran_get_version_6():
    '''Test gfortran 6.1.0 version detection.'''
    full_output = dedent("""
        GNU Fortran (GCC) 6.1.0
        Copyright (C) 2016 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run", mock.Mock(return_value=full_output)):
        assert gfortran.get_version() == (6, 1, 0)


def test_gfortran_get_version_8():
    '''Test gfortran 8.5.0 version detection.'''
    full_output = dedent("""
        GNU Fortran (conda-forge gcc 8.5.0-16) 8.5.0
        Copyright (C) 2018 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run", mock.Mock(return_value=full_output)):
        assert gfortran.get_version() == (8, 5, 0)


def test_gfortran_get_version_10():
    '''Test gfortran 10.4.0 version detection.'''
    full_output = dedent("""
        GNU Fortran (conda-forge gcc 10.4.0-16) 10.4.0
        Copyright (C) 2020 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run", mock.Mock(return_value=full_output)):
        assert gfortran.get_version() == (10, 4, 0)


def test_gfortran_get_version_12():
    '''Test gfortran 12.1.0 version detection.'''
    full_output = dedent("""
        GNU Fortran (conda-forge gcc 12.1.0-16) 12.1.0
        Copyright (C) 2022 Free Software Foundation, Inc.
        This is free software; see the source for copying conditions.  There is NO
        warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_output)):
        assert gfortran.get_version() == (12, 1, 0)


def test_gfortran_get_version_with_ifort_string():
    '''Tests the gfortran class with an ifort version output.'''
    full_output = dedent("""
        ifort (IFORT) 14.0.3 20140422
        Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

    """)
    gfortran = Gfortran()
    with mock.patch.object(gfortran, "run",
                           mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            gfortran.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# icc
# ============================================================================
def test_icc():
    '''Tests the icc class.'''
    icc = Icc()
    assert icc.name == "icc"
    assert isinstance(icc, CCompiler)
    assert icc.category == Category.C_COMPILER
    assert not icc.mpi


def test_icc_get_version():
    '''Tests the icc class get_version method.'''
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    icc = Icc()
    with mock.patch.object(icc, "run", mock.Mock(return_value=full_output)):
        assert icc.get_version() == (2021, 10, 0)


def test_icc_get_version_with_gcc_string():
    '''Tests the icc class with a GCC version output.'''
    full_output = dedent("""
        gcc (GCC) 8.5.0 20210514 (Red Hat 8.5.0-20)
        Copyright (C) 2018 Free Software Foundation, Inc.
    """)
    icc = Icc()
    with mock.patch.object(icc, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            icc.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# ifort
# ============================================================================
def test_ifort():
    '''Tests the ifort class.'''
    ifort = Ifort()
    assert ifort.name == "ifort"
    assert isinstance(ifort, FortranCompiler)
    assert ifort.category == Category.FORTRAN_COMPILER
    assert not ifort.mpi


def test_ifort_get_version_14():
    '''Test ifort 14.0.3 version detection.'''
    full_output = dedent("""
        ifort (IFORT) 14.0.3 20140422
        Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        assert ifort.get_version() == (14, 0, 3)


def test_ifort_get_version_15():
    '''Test ifort 15.0.2 version detection.'''
    full_output = dedent("""
        ifort (IFORT) 15.0.2 20150121
        Copyright (C) 1985-2015 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        assert ifort.get_version() == (15, 0, 2)


def test_ifort_get_version_17():
    '''Test ifort 17.0.7 version detection.'''
    full_output = dedent("""
        ifort (IFORT) 17.0.7 20180403
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        assert ifort.get_version() == (17, 0, 7)


def test_ifort_get_version_19():
    '''Test ifort 19.0.0.117 version detection.'''
    full_output = dedent("""
        ifort (IFORT) 19.0.0.117 20180804
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        assert ifort.get_version() == (19, 0, 0, 117)


def test_ifort_get_version_with_icc_string():
    '''Tests the ifort class with an icc version output.'''
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            ifort.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


@pytest.mark.parametrize("version", ["5.15f.2",
                                     ".0.5.1",
                                     "0.5.1.",
                                     "0.5..1"])
def test_ifort_get_version_invalid_version(version):
    '''Tests the ifort class with an ifort version string that contains an
    invalid version number.'''
    full_output = dedent(f"""
        ifort (IFORT) {version} 20140422
        Copyright (C) 1985-2014 Intel Corporation.  All rights reserved.

    """)
    ifort = Ifort()
    with mock.patch.object(ifort, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            ifort.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# icx
# ============================================================================
def test_icx():
    '''Tests the icx class.'''
    icx = Icx()
    assert icx.name == "icx"
    assert isinstance(icx, CCompiler)
    assert icx.category == Category.C_COMPILER
    assert not icx.mpi


def test_icx_get_version_2023():
    '''Test icx 2023.0.0 version detection.'''
    full_output = dedent("""
Intel(R) oneAPI DPC++/C++ Compiler 2023.0.0 (2023.0.0.20221201)
Target: x86_64-unknown-linux-gnu
Thread model: posix
InstalledDir: /opt/intel/oneapi/compiler/2023.0.0/linux/bin-llvm
Configuration file: /opt/intel/oneapi/compiler/2023.0.0/linux/bin-llvm/"""
                         """../bin/icx.cfg

    """)
    icx = Icx()
    with mock.patch.object(icx, "run", mock.Mock(return_value=full_output)):
        assert icx.get_version() == (2023, 0, 0)


def test_icx_get_version_with_icc_string():
    '''Tests the icx class with an icc version output.'''
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    icx = Icx()
    with mock.patch.object(icx, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            icx.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# ifx
# ============================================================================
def test_ifx():
    '''Tests the ifx class.'''
    ifx = Ifx()
    assert ifx.name == "ifx"
    assert isinstance(ifx, FortranCompiler)
    assert ifx.category == Category.FORTRAN_COMPILER
    assert not ifx.mpi


def test_ifx_get_version_2023():
    '''Test ifx 2023.0.0 version detection.'''
    full_output = dedent("""
ifx (IFX) 2023.0.0 20221201
Copyright (C) 1985-2022 Intel Corporation. All rights reserved.

    """)
    ifx = Ifx()
    with mock.patch.object(ifx, "run", mock.Mock(return_value=full_output)):
        assert ifx.get_version() == (2023, 0, 0)


def test_ifx_get_version_with_ifort_string():
    '''Tests the ifx class with an icc version output.'''
    full_output = dedent("""
        ifort (IFORT) 19.0.0.117 20180804
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    ifx = Ifx()
    with mock.patch.object(ifx, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            ifx.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# nvc
# ============================================================================
def test_nvc():
    '''Tests the nvc class.'''
    nvc = Nvc()
    assert nvc.name == "nvc"
    assert isinstance(nvc, CCompiler)
    assert nvc.category == Category.C_COMPILER
    assert not nvc.mpi


def test_nvc_get_version_23_5_0():
    '''Test nvc 23.5.0 version detection.'''
    full_output = dedent("""

nvc 23.5-0 64-bit target on x86-64 Linux -tp icelake-server
NVIDIA Compilers and Tools
Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
    """)
    nvc = Nvc()
    with mock.patch.object(nvc, "run", mock.Mock(return_value=full_output)):
        assert nvc.get_version() == (23, 5)


def test_nvc_get_version_with_icc_string():
    '''Tests the nvc class with an icc version output.'''
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    nvc = Nvc()
    with mock.patch.object(nvc, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            nvc.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# nvfortran
# ============================================================================
def test_nvfortran():
    '''Tests the nvfortran class.'''
    nvfortran = Nvfortran()
    assert nvfortran.name == "nvfortran"
    assert isinstance(nvfortran, FortranCompiler)
    assert nvfortran.category == Category.FORTRAN_COMPILER
    assert not nvfortran.mpi


def test_nvfortran_get_version_23_5_0():
    '''Test nvfortran 23.5 version detection.'''
    full_output = dedent("""

nvfortran 23.5-0 64-bit target on x86-64 Linux -tp icelake-server
NVIDIA Compilers and Tools
Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES.  All rights reserved.
    """)
    nvfortran = Nvfortran()
    with mock.patch.object(nvfortran, "run",
                           mock.Mock(return_value=full_output)):
        assert nvfortran.get_version() == (23, 5)


def test_nvfortran_get_version_with_ifort_string():
    '''Tests the nvfortran class with an icc version output.'''
    full_output = dedent("""
        ifort (IFORT) 19.0.0.117 20180804
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    nvfortran = Nvfortran()
    with mock.patch.object(nvfortran, "run",
                           mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            nvfortran.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# Craycc
# ============================================================================
def test_craycc():
    '''Tests the Craycc class.'''
    craycc = Craycc()
    assert craycc.name == "craycc-cc"
    assert isinstance(craycc, CCompiler)
    assert craycc.category == Category.C_COMPILER
    assert craycc.mpi


def test_craycc_get_version_8_7_0():
    '''Test craycc .23.5 version detection.'''
    full_output = dedent("""
Cray C : Version 8.7.0  Tue Jul 23, 2024  07:39:46

    """)
    craycc = Craycc()
    with mock.patch.object(craycc, "run", mock.Mock(return_value=full_output)):
        assert craycc.get_version() == (8, 7, 0)


def test_craycc_get_version_2023():
    '''Test craycc .23.5 version detection.'''
    full_output = dedent("""
Cray clang version 15.0.1  (66f7391d6a03cf932f321b9f6b1d8612ef5f362c)

Target: x86_64-unknown-linux-gnu

Thread model: posix

InstalledDir: /opt/cray/pe/cce/15.0.1/cce-clang/x86_64/share/../bin

Found candidate GCC installation: /opt/gcc/10.3.0/snos/lib/gcc/x86_64-"""
                         """suse-linux/10.3.0

Selected GCC installation: /opt/gcc/10.3.0/snos/lib/gcc/x86_64-suse-"""
                         """linux/10.3.0

Candidate multilib: .;@m64

Selected multilib: .;@m64

OFFICIAL
    """)
    craycc = Craycc()
    with mock.patch.object(craycc, "run", mock.Mock(return_value=full_output)):
        assert craycc.get_version() == (15, 0, 1)


def test_craycc_get_version_with_icc_string():
    '''Tests the Craycc class with an icc version output.'''
    full_output = dedent("""
        icc (ICC) 2021.10.0 20230609
        Copyright (C) 1985-2023 Intel Corporation.  All rights reserved.

    """)
    craycc = Craycc()
    with mock.patch.object(craycc, "run", mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            craycc.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))


# ============================================================================
# Crayftn
# ============================================================================
def test_crayftn():
    '''Tests the Crayftn class.'''
    crayftn = Crayftn()
    assert crayftn.name == "crayftn-ftn"
    assert isinstance(crayftn, FortranCompiler)
    assert crayftn.category == Category.FORTRAN_COMPILER
    assert crayftn.mpi


def test_crayftn_get_version_8_7_0():
    '''Test crayftn .23.5 version detection.'''
    full_output = dedent("""
Cray Fortran : Version 8.7.0  Tue Jul 23, 2024  07:39:25
    """)
    crayftn = Crayftn()
    with mock.patch.object(crayftn, "run",
                           mock.Mock(return_value=full_output)):
        assert crayftn.get_version() == (8, 7, 0)


def test_crayftn_get_version_15_0_1():
    '''Test Crayftn 15.0.1 version detection.'''
    full_output = dedent("""
Cray Fortran : Version 15.0.1  Tue Jul 23, 2024  07:39:25
    """)
    crayftn = Crayftn()
    with mock.patch.object(crayftn, "run",
                           mock.Mock(return_value=full_output)):
        assert crayftn.get_version() == (15, 0, 1)


def test_crayftn_get_version_with_ifort_string():
    '''Tests the crayftn class with an icc version output.'''
    full_output = dedent("""
        ifort (IFORT) 19.0.0.117 20180804
        Copyright (C) 1985-2018 Intel Corporation.  All rights reserved.

    """)
    crayftn = Crayftn()
    with mock.patch.object(crayftn, "run",
                           mock.Mock(return_value=full_output)):
        with pytest.raises(RuntimeError) as err:
            crayftn.get_version()
        assert ("Unexpected version output format for compiler"
                in str(err.value))

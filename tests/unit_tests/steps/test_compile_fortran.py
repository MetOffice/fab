import os
from pathlib import Path
from textwrap import dedent
from unittest import mock
from unittest.mock import call

import pytest

from fab.build_config import BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES

from fab.dep_tree import AnalysedFile
from fab.steps.compile_fortran import CompileFortran, get_compiler, _get_compiler_version, get_mod_hashes
from fab.util import CompiledFile


@pytest.fixture()
def compiler():
    with mock.patch('fab.steps.compile_fortran._get_compiler_version', return_value='1.2.3'):
        compiler = CompileFortran(compiler="foo_cc")
    return compiler


@pytest.fixture
def analysed_files():
    a = AnalysedFile(fpath=Path('a.f90'), file_deps={Path('b.f90')}, file_hash=0)
    b = AnalysedFile(fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=0)
    c = AnalysedFile(fpath=Path('c.f90'), file_hash=0)
    return a, b, c


@pytest.fixture
def artefact_store(analysed_files):
    build_tree = {af.fpath: af for af in analysed_files}
    artefact_store = {BUILD_TREES: {None: build_tree}}
    return artefact_store


class Test_compile_pass(object):

    def test_vanilla(self, compiler, analysed_files):
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        run_mp_results = [mock.Mock(spec=CompiledFile, input_fpath=Path('b.f90'))]

        with mock.patch('fab.steps.compile_fortran.CompileFortran.run_mp', return_value=run_mp_results):
            with mock.patch('fab.steps.compile_fortran.get_mod_hashes'):
                uncompiled_result = compiler.compile_pass(compiled=compiled, uncompiled=uncompiled, config=None)

        assert Path('b.f90') in compiled
        assert list(uncompiled_result)[0].fpath == Path('a.f90')


class Test_get_compile_next(object):

    def test_vanilla(self, compiler, analysed_files):
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        compile_next = compiler.get_compile_next(compiled, uncompiled)

        assert compile_next == {b, }

    def test_unable_to_compile_anything(self, compiler, analysed_files):
        # like vanilla, except c hasn't been compiled
        a, b, c = analysed_files
        to_compile = {a, b}
        already_compiled_files = {}

        with pytest.raises(ValueError):
            compiler.get_compile_next(already_compiled_files, to_compile)


class Test_store_artefacts(object):

    def test_vanilla(self, compiler):

        # what we wanted to compile
        build_trees = {
            'root1': [
                mock.Mock(fpath=Path('root1.f90')),
                mock.Mock(fpath=Path('dep1.f90')),
            ],
            'root2': [
                mock.Mock(fpath=Path('root2.f90')),
                mock.Mock(fpath=Path('dep2.f90')),
            ],
        }

        # what we actually compiled
        compiled_files = {
            Path('root1.f90'): mock.Mock(input_fpath=Path('root1.f90'), output_fpath=Path('root1.o')),
            Path('dep1.f90'): mock.Mock(input_fpath=Path('dep1.f90'), output_fpath=Path('dep1.o')),
            Path('root2.f90'): mock.Mock(input_fpath=Path('root2.f90'), output_fpath=Path('root2.o')),
            Path('dep2.f90'): mock.Mock(input_fpath=Path('dep2.f90'), output_fpath=Path('dep2.o')),
        }

        # where it stores the results
        artefact_store = {}

        compiler.store_artefacts(compiled_files=compiled_files, build_trees=build_trees, artefact_store=artefact_store)

        assert artefact_store == {
            OBJECT_FILES: {
                'root1': {Path('root1.o'), Path('dep1.o')},
                'root2': {Path('root2.o'), Path('dep2.o')},
            }
        }


class Test_process_file(object):

    def content(self, flags=None):

        with mock.patch('fab.steps.compile_fortran._get_compiler_version', return_value='1.2.3'):
            compiler = CompileFortran(compiler="foo_cc")

        flags = flags or ['flag1', 'flag2']
        compiler.flags = mock.Mock()
        compiler.flags.flags_for_path.return_value = flags

        compiler._mod_hashes = {'mod_dep_1': 12345, 'mod_dep_2': 23456}
        compiler._config = BuildConfig('proj', fab_workspace=Path('/fab'))

        analysed_file = AnalysedFile(fpath=Path('foofile'), file_hash=34567)
        analysed_file.add_module_dep('mod_dep_1')
        analysed_file.add_module_dep('mod_dep_2')
        analysed_file.add_module_def('mod_def_1')
        analysed_file.add_module_def('mod_def_2')

        obj_combo_hash = '1eb0c2d19'
        mods_combo_hash = '1747a9a0f'

        return compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash

    # Developer's note: If the "mods combo hash" changes you'll get an unhelpful message from pytest.
    # It'll come from this function but pytest won't tell you that.
    # You'll have to set a breakpoint here to see the changed hash in calls to mock_copy.
    def ensure_mods_stored(self, mock_copy, mods_combo_hash):
        # Make sure the newly created mod files were copied TO the prebuilds folder.
        mock_copy.assert_has_calls(
            calls=[
                call(Path('/fab/proj/build_output/mod_def_1.mod'),
                     Path(f'/fab/proj/build_output/_prebuild/mod_def_1.{mods_combo_hash}.mod')),
                call(Path('/fab/proj/build_output/mod_def_2.mod'),
                     Path(f'/fab/proj/build_output/_prebuild/mod_def_2.{mods_combo_hash}.mod')),
            ],
            any_order=True,
        )

    def ensure_mods_restored(self, mock_copy, mods_combo_hash):
        # make sure previously built mod files were copied FROM the prebuilds folder
        mock_copy.assert_has_calls(
            calls=[
                call(Path(f'/fab/proj/build_output/_prebuild/mod_def_1.{mods_combo_hash}.mod'),
                     Path('/fab/proj/build_output/mod_def_1.mod')),
                call(Path(f'/fab/proj/build_output/_prebuild/mod_def_2.{mods_combo_hash}.mod'),
                     Path('/fab/proj/build_output/mod_def_2.mod')),
            ],
            any_order=True,
        )

    def test_without_prebuild(self):
        # call compile_file() and return a CompiledFile
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', return_value=False):  # no output files exist
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_with_prebuild(self):
        # If the mods and obj are prebuilt, don't compile.
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', return_value=True):  # mod def files and obj file all exist
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_not_called()
        self.ensure_mods_restored(mock_copy, mods_combo_hash)

    def test_file_hash(self):
        # Changing the source hash must change the combo hash for the mods and obj.
        # Note: This test adds 1 to the analysed files hash. We're using checksums so
        #       the resulting object file and mod file combo hashes can be expected to increase by 1 too.
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        analysed_file.file_hash += 1
        obj_combo_hash = f'{int(obj_combo_hash, 16) + 1:x}'
        mods_combo_hash = f'{int(mods_combo_hash, 16) + 1:x}'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_flags_hash(self):
        # changing the flags must change the object combo hash, but not the mods combo hash
        compiler, flags, analysed_file, _, mods_combo_hash = self.content(flags=['flag1', 'flag3'])
        obj_combo_hash = '1ebce92ee'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_deps_hash(self):
        # Changing the checksums of any mod dependency must change the object combo hash but not the mods combo hash.
        # Note the difference between mods we depend on and mods we define.
        # The mods we define are not affected by the mods we depend on.
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        compiler._mod_hashes['mod_dep_1'] += 1
        obj_combo_hash = f'{int(obj_combo_hash, 16) + 1:x}'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_compiler_hash(self):
        # changing the compiler must change the combo hash for the mods and obj
        compiler, flags, analysed_file, _, _ = self.content()

        compiler.compiler = 'bar_cc'
        obj_combo_hash = '16c5a5a06'
        mods_combo_hash = 'f5c8c6fc'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_compiler_version_hash(self):
        # changing the compiler version must change the combo hash for the mods and obj
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        compiler.compiler_version = '1.2.4'
        obj_combo_hash = '17927b778'
        mods_combo_hash = '10296246e'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_mod_missing(self):
        # if one of the mods we define is not present, we must recompile
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[False, True, True]):  # one mod file missing
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

    def test_obj_missing(self):
        # the object file we define is not present, so we must recompile
        compiler, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # object file missing
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)


class test_constructor(object):

    def test_bare(self):
        with mock.patch.dict(os.environ, FC='foofc', FFLAGS=''):
            cf = CompileFortran()
        assert cf.compiler == 'foofc'
        assert cf.flags.common_flags == []

    def test_with_flags(self):
        with mock.patch.dict(os.environ, FC='foofc -monty', FFLAGS='--foo --bar'):
            cf = CompileFortran()
        assert cf.compiler == 'foofc'
        assert cf.flags.common_flags == ['-monty', '--foo', '--bar']

    def test_gfortran_managed_flags(self):
        with mock.patch.dict(os.environ, FC='gfortran -c', FFLAGS='-J /mods'):
            cf = CompileFortran()
        assert cf.compiler == 'gfortran'
        assert cf.flags.common_flags == []

    def test_ifort_managed_flags(self):
        with mock.patch.dict(os.environ, FC='gfortran -c', FFLAGS='-module /mods'):
            cf = CompileFortran()
        assert cf.compiler == 'ifort'
        assert cf.flags.common_flags == []

    def test_as_argument(self):
        cf = CompileFortran(compiler='foofc -c')
        assert cf.compiler == 'foofc'
        assert cf.flags.common_flags == ['-c']

    def test_precedence(self):
        with mock.patch.dict(os.environ, FC='foofc'):
            cf = CompileFortran(compiler='barfc')
        assert cf.compiler == 'barfc'

    def test_no_compiler(self):
        with mock.patch.dict(os.environ, FC=''):
            with pytest.raises(ValueError):
                CompileFortran()

    def test_unknown_compiler(self):
        with mock.patch.dict(os.environ, FC='foofc -c', FFLAGS='-J /mods'):
            cf = CompileFortran()
        assert cf.compiler == 'foofc'
        assert cf.flags.common_flags == ['-c', '-J', '/mods']


class test_get_compiler(object):

    def test_without_flag(self):
        assert get_compiler('gfortran') == ('gfortran', [])

    def test_with_flag(self):
        assert get_compiler('gfortran -c') == ('gfortran', ['-c'])


class Test_get_compiler_version(object):

    def _check(self, full_version_string, expect):
        with mock.patch('fab.steps.compile_fortran.run_command', return_value=full_version_string):
            result = _get_compiler_version(None)
        assert result == expect

    def test_command_failure(self):
        # if the command fails, we must return an empty string, not None, so it can still be hashed
        with mock.patch('fab.steps.compile_fortran.run_command', side_effect=RuntimeError()):
            assert _get_compiler_version(None) == '', 'expected empty string'

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


class Test_get_mod_hashes(object):

    def test_vanilla(self):
        # get a hash value for every module in the analysed file
        analysed_files = {
            mock.Mock(module_defs=['foo', 'bar']),
        }

        config = BuildConfig('proj', fab_workspace=Path('/fab_workspace'))

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            with mock.patch(
                    'fab.steps.compile_fortran.file_checksum',
                    side_effect=[mock.Mock(file_hash=123), mock.Mock(file_hash=456)]):
                result = get_mod_hashes(analysed_files=analysed_files, config=config)

        assert result == {'foo': 123, 'bar': 456}

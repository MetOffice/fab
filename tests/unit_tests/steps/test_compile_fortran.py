import os
from pathlib import Path
from typing import Dict
from unittest import mock
from unittest.mock import call

import pytest

from fab.build_config import BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.parse.fortran import AnalysedFortran
from fab.steps.compile_fortran import compile_pass, get_compile_next, get_fortran_compiler, \
    get_mod_hashes, handle_compiler_args, MpCommonArgs, process_file, store_artefacts
from fab.steps.preprocess import get_fortran_preprocessor
from fab.util import CompiledFile


@pytest.fixture
def analysed_files():
    a = AnalysedFortran(fpath=Path('a.f90'), file_deps={Path('b.f90')}, file_hash=0)
    b = AnalysedFortran(fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=0)
    c = AnalysedFortran(fpath=Path('c.f90'), file_hash=0)
    return a, b, c


@pytest.fixture
def artefact_store(analysed_files):
    build_tree = {af.fpath: af for af in analysed_files}
    artefact_store = {BUILD_TREES: {None: build_tree}}
    return artefact_store


class Test_compile_pass(object):

    def test_vanilla(self, analysed_files):
        # make sure it compiles b only
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        run_mp_results = [
            (
                mock.Mock(spec=CompiledFile, input_fpath=Path('b.f90')),
                [Path('/prebuild/b.123.o')]
            )
        ]

        # this gets filled in
        mod_hashes: Dict[str, int] = {}

        config = BuildConfig('proj')
        with mock.patch('fab.steps.compile_fortran.run_mp', return_value=run_mp_results):
            with mock.patch('fab.steps.compile_fortran.get_mod_hashes'):
                uncompiled_result = compile_pass(config=config, compiled=compiled, uncompiled=uncompiled,
                                                 mod_hashes=mod_hashes, mp_common_args=None)

        assert Path('a.f90') not in compiled
        assert Path('b.f90') in compiled
        assert list(uncompiled_result)[0].fpath == Path('a.f90')


class Test_get_compile_next(object):

    def test_vanilla(self, analysed_files):
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        compile_next = get_compile_next(compiled, uncompiled)

        assert compile_next == {b, }

    def test_unable_to_compile_anything(self, analysed_files):
        # like vanilla, except c hasn't been compiled
        a, b, c = analysed_files
        to_compile = {a, b}
        already_compiled_files = {}

        with pytest.raises(ValueError):
            get_compile_next(already_compiled_files, to_compile)


class Test_store_artefacts(object):

    def test_vanilla(self):

        # what we wanted to compile
        build_lists = {
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

        store_artefacts(compiled_files=compiled_files, build_lists=build_lists, artefact_store=artefact_store)

        assert artefact_store == {
            OBJECT_FILES: {
                'root1': {Path('root1.o'), Path('dep1.o')},
                'root2': {Path('root2.o'), Path('dep2.o')},
            }
        }


class Test_process_file(object):

    def content(self, flags=None):

        flags = flags or ['flag1', 'flag2']
        flags_config = mock.Mock()
        flags_config.flags_for_path.return_value = flags

        analysed_file = AnalysedFortran(fpath=Path('foofile'), file_hash=34567)
        analysed_file.add_module_dep('mod_dep_1')
        analysed_file.add_module_dep('mod_dep_2')
        analysed_file.add_module_def('mod_def_1')
        analysed_file.add_module_def('mod_def_2')

        obj_combo_hash = '1eb0c2d19'
        mods_combo_hash = '1747a9a0f'

        mp_common_args = MpCommonArgs(
            config=BuildConfig('proj', fab_workspace=Path('/fab')),
            flags=flags_config,
            compiler='foo_cc',
            compiler_version='1.2.3',
            mod_hashes={'mod_dep_1': 12345, 'mod_dep_2': 23456},
            two_stage_flag=False,
            stage=None,
        )

        return mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash

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
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        flags_config = mock.Mock()
        flags_config.flags_for_path.return_value = flags

        with mock.patch('pathlib.Path.exists', return_value=False):  # no output files exist
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        # check we got the expected compilation result
        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)

        # check we called the tool correctly
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)

        # check the correct mod files were copied to the prebuild folder
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_with_prebuild(self):
        # If the mods and obj are prebuilt, don't compile.
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', return_value=True):  # mod def files and obj file all exist
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_not_called()
        self.ensure_mods_restored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_file_hash(self):
        # Changing the source hash must change the combo hash for the mods and obj.
        # Note: This test adds 1 to the analysed files hash. We're using checksums so
        #       the resulting object file and mod file combo hashes can be expected to increase by 1 too.
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        analysed_file._file_hash += 1
        obj_combo_hash = f'{int(obj_combo_hash, 16) + 1:x}'
        mods_combo_hash = f'{int(mods_combo_hash, 16) + 1:x}'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_flags_hash(self):
        # changing the flags must change the object combo hash, but not the mods combo hash
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content(flags=['flag1', 'flag3'])
        obj_combo_hash = '1ebce92ee'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_deps_hash(self):
        # Changing the checksums of any mod dependency must change the object combo hash but not the mods combo hash.
        # Note the difference between mods we depend on and mods we define.
        # The mods we define are not affected by the mods we depend on.
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        mp_common_args.mod_hashes['mod_dep_1'] += 1
        obj_combo_hash = f'{int(obj_combo_hash, 16) + 1:x}'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_compiler_hash(self):
        # changing the compiler must change the combo hash for the mods and obj
        mp_common_args, flags, analysed_file, _, _ = self.content()

        mp_common_args.compiler = 'bar_cc'
        obj_combo_hash = '16c5a5a06'
        mods_combo_hash = 'f5c8c6fc'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_compiler_version_hash(self):
        # changing the compiler version must change the combo hash for the mods and obj
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        mp_common_args.compiler_version = '1.2.4'
        obj_combo_hash = '17927b778'
        mods_combo_hash = '10296246e'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_mod_missing(self):
        # if one of the mods we define is not present, we must recompile
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[False, True, True]):  # one mod file missing
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_obj_missing(self):
        # the object file we define is not present, so we must recompile
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # object file missing
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }


class Test_constructor(object):

    def test_bare(self):
        with mock.patch.dict(os.environ, FC='foofc', clear=True):
            with mock.patch('fab.steps.compile_fortran.get_compiler_version'):
                compiler, compiler_version, flags = handle_compiler_args()
        assert compiler == 'foofc'
        assert flags.common_flags == []

    def test_with_flags(self):
        with mock.patch.dict(os.environ, FC='foofc -monty', FFLAGS='--foo --bar'):
            with mock.patch('fab.steps.compile_fortran.get_compiler_version'):
                compiler, compiler_version, flags = handle_compiler_args()
        assert compiler == 'foofc'
        assert flags.common_flags == ['-monty', '--foo', '--bar']

    def test_gfortran_managed_flags(self):
        with mock.patch.dict(os.environ, FC='gfortran -c', FFLAGS='-J /mods'):
            with mock.patch('fab.steps.compile_fortran.get_compiler_version'), \
                 pytest.warns(UserWarning, match="removing managed flag"):
                compiler, compiler_version, flags = handle_compiler_args()
        assert compiler == 'gfortran'
        assert flags.common_flags == []

    def test_ifort_managed_flags(self):
        with mock.patch.dict(os.environ, FC='ifort -c', FFLAGS='-module /mods'):
            with mock.patch('fab.steps.compile_fortran.get_compiler_version'), \
                 pytest.warns(UserWarning, match="removing managed flag"):
                compiler, compiler_version, flags = handle_compiler_args()
        assert compiler == 'ifort'
        assert flags.common_flags == []

    def test_no_compiler(self):
        with mock.patch.dict(os.environ, clear=True):
            with mock.patch('fab.steps.compile_fortran.run_command', side_effect=RuntimeError):
                with pytest.raises(RuntimeError):
                    handle_compiler_args()

    def test_unknown_compiler(self):
        with mock.patch.dict(os.environ, FC='foofc -c', FFLAGS='-J /mods'):
            with mock.patch('fab.steps.compile_fortran.get_compiler_version'):
                compiler, compiler_version, flags = handle_compiler_args()
        assert compiler == 'foofc'
        assert flags.common_flags == ['-c', '-J', '/mods']

    # todo: test with args - handle_compiler_args(common_flags, path_flags)


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


class Test_get_fortran_preprocessor(object):

    def test_from_env(self):
        with mock.patch.dict(os.environ, values={'FPP': 'foo_pp --foo'}):
            fpp, fpp_flags = get_fortran_preprocessor()

        assert fpp == 'foo_pp'
        assert fpp_flags == ['--foo', '-P']

    def test_empty_env_fpp(self):
        # test with an empty FPP env var, and only fpp available at the command line
        def mock_run_command(command):
            if 'fpp' not in command:
                raise RuntimeError('foo')

        with mock.patch.dict(os.environ, clear=True):
            with mock.patch('fab.steps.preprocess.run_command', side_effect=mock_run_command):
                fpp, fpp_flags = get_fortran_preprocessor()

        assert fpp == 'fpp'
        assert fpp_flags == ['-P']

    def test_empty_env_cpp(self):
        # test with an empty FPP env var, and only cpp available at the command line
        def mock_run_command(command):
            if 'cpp' not in command:
                raise RuntimeError('foo')

        with mock.patch.dict(os.environ, clear=True):
            with mock.patch('fab.steps.preprocess.run_command', side_effect=mock_run_command):
                fpp, fpp_flags = get_fortran_preprocessor()

        assert fpp == 'cpp'
        assert fpp_flags == ['-traditional-cpp', '-P']


class Test_get_fortran_compiler(object):

    def test_from_env(self):
        with mock.patch.dict(os.environ, values={'FC': 'foo_c --foo'}):
            fc, fc_flags = get_fortran_compiler()

        assert fc == 'foo_c'
        assert fc_flags == ['--foo']

    def test_empty_env_gfortran(self):
        def mock_run_command(command):
            if 'gfortran' not in command:
                raise RuntimeError('foo')

        with mock.patch.dict(os.environ, clear=True):
            with mock.patch('fab.steps.compile_fortran.run_command', side_effect=mock_run_command):
                fc, fc_flags = get_fortran_compiler()

        assert fc == 'gfortran'
        assert fc_flags == []

    def test_empty_env_ifort(self):
        def mock_run_command(command):
            if 'ifort' not in command:
                raise RuntimeError('foo')

        with mock.patch.dict(os.environ, clear=True):
            with mock.patch('fab.steps.compile_fortran.run_command', side_effect=mock_run_command):
                fc, fc_flags = get_fortran_compiler()

        assert fc == 'ifort'
        assert fc_flags == []

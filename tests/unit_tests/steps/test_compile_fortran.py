from pathlib import Path
from typing import Dict
from unittest import mock
from unittest.mock import call

import pytest

from fab.build_config import BuildConfig, FlagsConfig
from fab.constants import BUILD_TREES, OBJECT_FILES
from fab.parse.fortran import AnalysedFortran
from fab.steps.compile_fortran import compile_pass, get_compile_next, \
    get_mod_hashes, MpCommonArgs, process_file, store_artefacts
from fab.tools import Categories, ToolBox
from fab.util import CompiledFile


# This avoids pylint warnings about Redefining names from outer scope
@pytest.fixture(name="analysed_files")
def fixture_analysed_files():
    a = AnalysedFortran(fpath=Path('a.f90'), file_deps={Path('b.f90')}, file_hash=0)
    b = AnalysedFortran(fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=0)
    c = AnalysedFortran(fpath=Path('c.f90'), file_hash=0)
    return a, b, c


@pytest.fixture(name="artefact_store")
def fixture_artefact_store(analysed_files):
    build_tree = {af.fpath: af for af in analysed_files}
    artefact_store = {BUILD_TREES: {None: build_tree}}
    return artefact_store


class TestCompilePass():

    def test_vanilla(self, analysed_files, tool_box: ToolBox):
        # make sure it compiles b only
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled: Dict[Path, CompiledFile] = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        run_mp_results = [
            (
                mock.Mock(spec=CompiledFile, input_fpath=Path('b.f90')),
                [Path('/prebuild/b.123.o')]
            )
        ]

        # this gets filled in
        mod_hashes: Dict[str, int] = {}

        config = BuildConfig('proj', tool_box)
        mp_common_args = MpCommonArgs(config, FlagsConfig(), {}, True)
        with mock.patch('fab.steps.compile_fortran.run_mp', return_value=run_mp_results):
            with mock.patch('fab.steps.compile_fortran.get_mod_hashes'):
                uncompiled_result = compile_pass(config=config, compiled=compiled, uncompiled=uncompiled,
                                                 mod_hashes=mod_hashes, mp_common_args=mp_common_args)

        assert Path('a.f90') not in compiled
        assert Path('b.f90') in compiled
        assert list(uncompiled_result)[0].fpath == Path('a.f90')


class TestGetCompileNext():

    def test_vanilla(self, analysed_files):
        a, b, c = analysed_files
        uncompiled = {a, b}
        compiled = {c.fpath: mock.Mock(input_fpath=c.fpath)}

        compile_next = get_compile_next(compiled, uncompiled)

        assert compile_next == {b}

    def test_unable_to_compile_anything(self, analysed_files):
        # like vanilla, except c hasn't been compiled
        a, b, _ = analysed_files
        to_compile = {a, b}
        already_compiled_files = {}

        with pytest.raises(ValueError):
            get_compile_next(already_compiled_files, to_compile)


class TestStoreArtefacts():

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


# This avoids pylint warnings about Redefining names from outer scope
@pytest.fixture(name="content")
def fixture_content(tool_box):
    flags = ['flag1', 'flag2']
    flags_config = mock.Mock()
    flags_config.flags_for_path.return_value = flags

    analysed_file = AnalysedFortran(fpath=Path('foofile'), file_hash=34567)
    analysed_file.add_module_dep('mod_dep_1')
    analysed_file.add_module_dep('mod_dep_2')
    analysed_file.add_module_def('mod_def_1')
    analysed_file.add_module_def('mod_def_2')

    obj_combo_hash = '17ef947fd'
    mods_combo_hash = '10867b4f3'
    mp_common_args = MpCommonArgs(
        config=BuildConfig('proj', tool_box, fab_workspace=Path('/fab')),
        flags=flags_config,
        mod_hashes={'mod_dep_1': 12345, 'mod_dep_2': 23456},
        syntax_only=False,
    )

    return (mp_common_args, flags, analysed_file, obj_combo_hash,
            mods_combo_hash)


class TestProcessFile():

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

    def test_without_prebuild(self, content):
        # call compile_file() and return a CompiledFile
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content

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
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)

        # check the correct mod files were copied to the prebuild folder
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_with_prebuild(self, content):
        # If the mods and obj are prebuilt, don't compile.
        mp_common_args, _, analysed_file, obj_combo_hash, mods_combo_hash = content

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

    def test_file_hash(self, content):
        # Changing the source hash must change the combo hash for the mods and obj.
        # Note: This test adds 1 to the analysed files hash. We're using checksums so
        #       the resulting object file and mod file combo hashes can be expected to increase by 1 too.
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content

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
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_flags_hash(self, content):
        # changing the flags must change the object combo hash, but not the mods combo hash
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content
        flags = ['flag1', 'flag3']
        mp_common_args.flags.flags_for_path.return_value = flags
        obj_combo_hash = '17fbbadd2'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_deps_hash(self, content):
        # Changing the checksums of any mod dependency must change the object combo hash but not the mods combo hash.
        # Note the difference between mods we depend on and mods we define.
        # The mods we define are not affected by the mods we depend on.
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content

        mp_common_args.mod_hashes['mod_dep_1'] += 1
        obj_combo_hash = f'{int(obj_combo_hash, 16) + 1:x}'

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_compiler_hash(self, content):
        # changing the compiler must change the combo hash for the mods and obj
        mp_common_args, flags, analysed_file, orig_obj_hash, orig_mods_hash = content
        compiler = mp_common_args.config.tool_box[Categories.FORTRAN_COMPILER]
        compiler._name += "xx"

        obj_combo_hash = '19dfa6c83'
        mods_combo_hash = '12768d979'
        assert obj_combo_hash != orig_obj_hash
        assert mods_combo_hash != orig_mods_hash

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_compiler_version_hash(self, content):
        # changing the compiler version must change the combo hash for the mods and obj
        mp_common_args, flags, analysed_file, orig_obj_hash, orig_mods_hash = content
        compiler = mp_common_args.config.tool_box[Categories.FORTRAN_COMPILER]
        compiler._version = "9.8.7"

        obj_combo_hash = '1a87f4e07'
        mods_combo_hash = '131edbafd'
        assert orig_obj_hash != obj_combo_hash
        assert orig_mods_hash != mods_combo_hash

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_mod_missing(self, content):
        # if one of the mods we define is not present, we must recompile
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content

        with mock.patch('pathlib.Path.exists', side_effect=[False, True, True]):  # one mod file missing
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }

    def test_obj_missing(self, content):
        # the object file we define is not present, so we must recompile
        mp_common_args, flags, analysed_file, obj_combo_hash, mods_combo_hash = content

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # object file missing
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy, \
                     pytest.warns(UserWarning, match="_metric_send_conn not set, cannot send metrics"):
                    res, artefacts = process_file((analysed_file, mp_common_args))

        expect_object_fpath = Path(f'/fab/proj/build_output/_prebuild/foofile.{obj_combo_hash}.o')
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(
            analysed_file.fpath, flags, output_fpath=expect_object_fpath, mp_common_args=mp_common_args)
        self.ensure_mods_stored(mock_copy, mods_combo_hash)

        # check the correct artefacts were returned
        pb = mp_common_args.config.prebuild_folder
        assert set(artefacts) == {
            pb / f'foofile.{obj_combo_hash}.o',
            pb / f'mod_def_2.{mods_combo_hash}.mod',
            pb / f'mod_def_1.{mods_combo_hash}.mod'
        }


class TestGetModHashes():
    '''Contains hashing-tests.'''

    def test_vanilla(self, tool_box):
        '''Test hashing. '''
        # get a hash value for every module in the analysed file
        analysed_files = {
            mock.Mock(module_defs=['foo', 'bar']),
        }

        config = BuildConfig('proj', tool_box,
                             fab_workspace=Path('/fab_workspace'))

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            with mock.patch(
                    'fab.steps.compile_fortran.file_checksum',
                    side_effect=[mock.Mock(file_hash=123), mock.Mock(file_hash=456)]):
                result = get_mod_hashes(analysed_files=analysed_files, config=config)

        assert result == {'foo': 123, 'bar': 456}

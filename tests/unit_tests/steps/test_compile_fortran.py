from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest

from fab.build_config import BuildConfig
from fab.constants import BUILD_TREES, OBJECT_FILES

from fab.dep_tree import AnalysedFile
from fab.steps.compile_fortran import CompileFortran
from fab.util import CompiledFile


@pytest.fixture()
def compiler():
    return CompileFortran(compiler="foo_cc")


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

        expect_object_fpath = Path('/fab/proj/build_output/_prebuild/foofile.161554537.o')

        return compiler, flags, analysed_file, expect_object_fpath

    def ensure_mods_stored(self, mock_copy, mods_combo_hash='eac3b22d'):
        # make sure the newly created mod files were copied TO the prebuilds folder
        mock_copy.assert_has_calls(
            calls=[
                call(Path('/fab/proj/build_output/mod_def_1.mod'),
                     Path(f'/fab/proj/build_output/_prebuild/mod_def_1.{mods_combo_hash}.mod')),
                call(Path('/fab/proj/build_output/mod_def_2.mod'),
                     Path(f'/fab/proj/build_output/_prebuild/mod_def_2.{mods_combo_hash}.mod')),
            ],
            any_order=True,
        )

    def ensure_mods_restored(self, mock_copy, mods_combo_hash='eac3b22d'):
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
        compiler, flags, analysed_file, expect_object_fpath = self.content()

        with mock.patch('pathlib.Path.exists', return_value=False):  # no output files exist
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy)

    def test_with_prebuild(self):
        # If the mods and obj are prebuilt, don't compile.
        compiler, flags, analysed_file, expect_object_fpath = self.content()

        with mock.patch('pathlib.Path.exists', return_value=True):  # mod def files and obj file all exist
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_not_called()
        self.ensure_mods_restored(mock_copy)

    def test_file_hash(self):
        # changing the source hash must change the combo hash for the mods and obj
        compiler, flags, analysed_file, expect_object_fpath = self.content()
        analysed_file.file_hash += 1
        expect_object_fpath = Path('/fab/proj/build_output/_prebuild/foofile.161554538.o')  # object combo hash += 1

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash='eac3b22e')  # mods combo hash += 1

    def test_flags_hash(self):
        # changing the flags must change the object combo hash, but not the mods combo hash
        compiler, flags, analysed_file, expect_object_fpath = self.content(flags=['flag1', 'flag3'])
        expect_object_fpath = Path('/fab/proj/build_output/_prebuild/foofile.16217ab0c.o')

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy)

    def test_deps_hash(self):
        # changing the checksums of any module dependency must change the object combo hash, but not the mods combo hash
        compiler, flags, analysed_file, expect_object_fpath = self.content()
        compiler._mod_hashes['mod_dep_1'] += 1
        expect_object_fpath = Path('/fab/proj/build_output/_prebuild/foofile.161554538.o')  # hash += 1

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy)

    def test_compiler_hash(self):
        # changing the compiler must change the combo hash for the mods and obj
        compiler, flags, analysed_file, expect_object_fpath = self.content()
        compiler.exe = 'bar_cc'
        expect_object_fpath = Path('/fab/proj/build_output/_prebuild/foofile.e2a37224.o')

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # mod files exist, obj file doesn't
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy, mods_combo_hash='6c11df1a')

    @pytest.mark.skip(reason='not yet implemented')
    def test_compiler_version_hash(self):
        # changing the compiler version must change the combo hash
        raise NotImplementedError

    def test_mod_missing(self):
        # one of the mods we define is not present, so we must recompile
        compiler, flags, analysed_file, expect_object_fpath = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[False, True, True]):  # one mod file missing
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy)

    def test_obj_missing(self):
        # the object file we define is not present, so we must recompile
        compiler, flags, analysed_file, expect_object_fpath = self.content()

        with mock.patch('pathlib.Path.exists', side_effect=[True, True, False]):  # object file missing
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                with mock.patch('shutil.copy2') as mock_copy:
                    res = compiler.process_file(analysed_file)

        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_object_fpath)
        mock_compile_file.assert_called_once_with(analysed_file, flags, output_fpath=expect_object_fpath)
        self.ensure_mods_stored(mock_copy)

# todo: test compile_file

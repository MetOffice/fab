from pathlib import Path
from unittest import mock

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
    a = AnalysedFile(fpath=Path('a.f90'), file_deps={Path('b.f90')}, file_hash=None)
    b = AnalysedFile(fpath=Path('b.f90'), file_deps={Path('c.f90')}, file_hash=None)
    c = AnalysedFile(fpath=Path('c.f90'), file_hash=None)
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

    # def test_vanilla(self, compiler):
    #     # ensure the compiler is called and the dep hashes are correct
    #     compiled_file, patches = self._common(compiler=compiler)
    #
    #     assert patches['compile_file'].call_count == 1
    #     assert compiled_file.module_deps_hashes == {'util': 456}
    #
    # def test_skip(self, compiler):
    #     # ensure the compiler is NOT called, and the dep hashes are still correct
    #     compiled_file, patches = self._common(compiler=compiler)
    #
    #     assert patches['compile_file'].call_count == 0
    #     assert compiled_file.module_deps_hashes == {'util': 456}
    #
    # def _common(self, compiler):
    #     analysed_file = AnalysedFile(fpath=Path('foofile'), file_hash=123)
    #     analysed_file.add_module_def('my_mod')
    #     analysed_file.add_module_dep('util')
    #
    #     with mock.patch.multiple(
    #         compiler,
    #         _mod_hashes={'util': 456},
    #         compile_file=mock.DEFAULT,
    #         _config=BuildConfig('fooproj', source_root=Path('foosrc')),
    #     ) as patches:
    #         compiled_file = compiler.process_file(analysed_file)
    #
    #     return compiled_file, patches

    # @pytest.fixture
    # def flags(self):
    #     flags = mock.Mock()
    #     flags.flags_for_path.return_value = ['flag1', 'flag2']
    #     return flags
    #
    # @pytest.fixture
    # def mod_hashes(self):
    #     return {'mod1': 123, 'mod2': 456}
    #
    # @pytest.fixture()
    # def compiler():
    #     compiler = CompileFortran(compiler="foo_cc")
    #     # compiler.flags = flags
    #     # compiler._mod_hashes = mod_hashes

    def test_vanilla(self):
        # call compile_file() and return a CompiledFile for a fresh compile

        compiler = CompileFortran(compiler="foo_cc")
        flags = ['flag1', 'flag2']
        compiler.flags = mock.Mock()
        compiler.flags.flags_for_path.return_value = flags
        compiler._mod_hashes = {'mod1': 123, 'mod2': 456}
        compiler._config = BuildConfig('proj', fab_workspace=Path('/fab'))

        analysed_file = AnalysedFile(fpath=Path('foofile'), file_hash=123)

        with mock.patch('pathlib.Path.exists', return_value=False):
            with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
                res = compiler.process_file(analysed_file)

        expect_output_fpath = Path('/fab/proj/build_output/_prebuild/foofile.1615432d2.o')

        mock_compile_file.assert_called_once_with(
            analysed_file, flags, output_fpath=expect_output_fpath)
        assert res == CompiledFile(input_fpath=analysed_file.fpath, output_fpath=expect_output_fpath)

    def test_no_change(self):
        # don't call compile_file(), but still return the same CompiledFile
        pass

    def test_file_hash(self):
        # changing the source must change the combo hash
        pass

    def test_flags_hash(self):
        # changing the flags must change the combo hash
        pass

    def test_deps_hash(self):
        # changing the checksums of any module dependency must change the combo hash
        pass

    def test_compiler_hash(self):
        # changing the compiler must change the combo hash
        pass

    @pytest.mark.skip(reason='not yet implemented')
    def test_compiler_version_hash(self):
        # changing the compiler version must change the combo hash
        raise NotImplementedError

    def test_mod_missing(self):
        # one of the mods we define is not present, so we must recompile
        pass

    def test_obj_missing(self):
        # the object file we define is not present, so we must recompile
        pass


class Test_recompile_check(object):

    @pytest.fixture
    def params(self, compiler):
        analysed_file = AnalysedFile(fpath=Path('mod.f90'), file_hash=111)
        analysed_file.add_module_def('mod')
        analysed_file.add_module_dep('foo')
        analysed_file.add_module_dep('bar')

        flags_hash = 222
        last_compile = mock.Mock(source_hash=111, flags_hash=222, module_deps_hashes={'foo': 333, 'bar': 444})

        compiler._config = BuildConfig('proj', fab_workspace=Path('/fab_workspace'))
        compiler._mod_hashes = {'foo': 333, 'bar': 444}

        return analysed_file, flags_hash, last_compile, compiler

    def test_first_encounter(self, compiler):
        result = compiler.recompile_check(analysed_file=None, flags_hash=None, last_compile=None)
        assert result == NO_PREVIOUS_RESULT

    def test_nothing_changed(self, params):
        analysed_file, flags_hash, last_compile, compiler = params

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert not recompile_reasons

    def test_source_changed(self, params):
        analysed_file, flags_hash, last_compile, compiler = params
        analysed_file.file_hash = 999

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert recompile_reasons == SOURCE_CHANGED

    def test_flags_changed(self, params):
        analysed_file, _, last_compile, compiler = params
        flags_hash = 999

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert recompile_reasons == FLAGS_CHANGED

    def test_mod_deps_changed(self, params):
        analysed_file, flags_hash, last_compile, compiler = params
        compiler._mod_hashes['bar'] = 999

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert recompile_reasons == MODULE_DEPENDENCIES_CHANGED

    def test_obj_missing(self, params):
        analysed_file, flags_hash, last_compile, compiler = params

        with mock.patch('pathlib.Path.exists', side_effect=[False, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert recompile_reasons == OBJECT_FILE_NOT_PRESENT

    def test_mod_defs_missing(self, params):
        analysed_file, flags_hash, last_compile, compiler = params

        with mock.patch('pathlib.Path.exists', side_effect=[True, False]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert recompile_reasons == MODULE_FILE_NOT_PRESENT

    def multiple_reasons(self, params):
        analysed_file, flags_hash, last_compile, compiler = params
        analysed_file.file_hash = 999
        flags_hash = 999

        with mock.patch('pathlib.Path.exists', side_effect=[True, True]):
            recompile_reasons = compiler.recompile_check(
                analysed_file=analysed_file, flags_hash=flags_hash, last_compile=last_compile)

        assert SOURCE_CHANGED in recompile_reasons
        assert FLAGS_CHANGED in recompile_reasons


# todo: test compile_file here? it's just glue

# todo: test write_compile_result & read_compile_result here - perhaps as integration tests?

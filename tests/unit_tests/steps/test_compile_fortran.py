from pathlib import Path
from unittest import mock

import pytest
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


class Test_get_compile_next(object):

    def test_vanilla(self, compiler, analysed_files):
        a, b, c = analysed_files
        to_compile = {a, b}
        already_compiled_files = {c.fpath}

        compile_next = compiler.get_compile_next(already_compiled_files, to_compile)

        assert compile_next == {b, }

    def test_unable_to_compile_anything(self, compiler, analysed_files):
        # like vanilla, except c hasn't been compiled
        a, b, c = analysed_files
        to_compile = {a, b}
        already_compiled_files = set([])

        with pytest.raises(RuntimeError):
            compiler.get_compile_next(already_compiled_files, to_compile)


class Test_run(object):

    def test_vanilla(self, compiler, analysed_files, artefact_store):

        def mp_return(items, func):
            return [CompiledFile(input_fpath=i.input_fpath, output_fpath=i.input_fpath.with_suffix('.o')) for i in items]

        with mock.patch('fab.steps.compile_fortran.CompileFortran.run_mp', side_effect=mp_return):
            compiler.run(artefact_store, config=None)

        compiled = artefact_store[OBJECT_FILES]
        # expected = [i.input_fpath.with_suffix('.o') for i in reversed(analysed_files)]
        expected = {None: {i.fpath.with_suffix('.o') for i in analysed_files}}
        assert compiled == expected

    def test_exception(self, compiler, analysed_files, artefact_store):
        # Like vanilla but run_mp returns an exception from the compiler.
        # All exceptions from a single pass are collated and raised together.

        def mp_return(items, func):
            return [Exception("Pretend it didn't compile") for i in items]

        with mock.patch('fab.steps.compile_fortran.CompileFortran.run_mp', side_effect=mp_return):
            with pytest.raises(RuntimeError):
                compiler.run(artefact_store, config=None)


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

        # where it stores the object paths
        artefact_store = {}

        compiler.store_artefacts(compiled_files=compiled_files, build_trees=build_trees, artefact_store=artefact_store)

        assert artefact_store == {
            OBJECT_FILES: {
                'root1': {Path('root1.o'), Path('dep1.o')},
                'root2': {Path('root2.o'), Path('dep2.o')},
            }
        }


class Test_comple_pass(object):

    def test_vanilla(self, compiler):

        compiled_files: Dict[Path, CompiledFile] = {
            Path(): mock.Mock(),
        }

        to_compile: List = [
            An
        ]

        config = {}

        compiler.compile_pass(compiled=compiled_files, uncompiled=to_compile, config=config)

    def test_last_pass(self, compiler):
        pass

    def test_nothing_compiled(self, compiler):
        pass

from pathlib import Path
from unittest import mock

import pytest

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

    def test_vanilla(self, compiler, analysed_files):
        artefact_store = {'build_tree': {af.fpath: af for af in analysed_files}}

        def mp_return(items, func):
            return [CompiledFile(analysed_file=i, output_fpath=i.fpath.with_suffix('.o')) for i in items]

        with mock.patch('fab.steps.compile_fortran.CompileFortran.run_mp', side_effect=mp_return):
            compiler.run(artefact_store, config=None)

        compiled = artefact_store['compiled_fortran']
        expected = [i.fpath.with_suffix('.o') for i in reversed(analysed_files)]
        assert compiled == expected

    def test_exception(self, compiler, analysed_files):
        # Like vanilla but run_mp returns an exception from the compiler.
        # All exceptions from a single pass are collated and raised together.
        artefact_store = {'build_tree': {af.fpath: af for af in analysed_files}}

        def mp_return(items, func):
            return [Exception("Pretend it didn't compile") for i in items]

        with mock.patch('fab.steps.compile_fortran.CompileFortran.run_mp', side_effect=mp_return):
            with pytest.raises(RuntimeError):
                compiler.run(artefact_store, config=None)

from pathlib import Path
from unittest import mock

import pytest
from fab.constants import BUILD_TREES

from fab.build_config import AddFlags

from fab.dep_tree import AnalysedFile
from fab.steps.compile_fortran import CompileFortran
# todo: we might have liked to reuse this from test_dep_tree
from fab.util import CompiledFile


@pytest.fixture
def src_tree():
    return {
        Path('src/foo.f90'): AnalysedFile(fpath=Path('src/foo.f90'), file_hash=None),
        Path('src/root.f90'): AnalysedFile(
            fpath=Path('src/root.f90'), file_deps={Path('src/a.f90'), Path('src/b.f90')}, file_hash=None),
        Path('src/a.f90'): AnalysedFile(fpath=Path('src/a.f90'), file_deps={Path('src/c.f90')}, file_hash=None),
        Path('src/b.f90'): AnalysedFile(fpath=Path('src/b.f90'), file_deps={Path('src/c.f90')}, file_hash=None),
        Path('src/c.f90'): AnalysedFile(fpath=Path('src/c.f90'), file_deps=set(), file_hash=None),
    }


class Test_run(object):

    # todo: almost identical to the c compiler test
    def test_vanilla(self, src_tree):
        # ensure the compile passes match the build tree

        config = mock.Mock(workspace=Path('foo/src'), multiprocessing=False)

        c_compiler = CompileFortran(
            compiler='gcc', common_flags=['-c'], path_flags=[AddFlags(match='foo/src/*', flags=['-Dhello'])])

        def foo(items, func):
            return [CompiledFile(af.input_fpath, output_fpath=None) for af in items]

        with mock.patch('fab.steps.Step.run_mp', side_effect=foo) as mock_run_mp:
            c_compiler.run(artefact_store={BUILD_TREES: {None: src_tree}}, config=config)

            # 1st pass
            mock_run_mp.assert_any_call(
                items={src_tree[Path('src/foo.f90')], src_tree[Path('src/c.f90')]}, func=mock.ANY)

            # 2nd pass
            mock_run_mp.assert_any_call(
                items={src_tree[Path('src/a.f90')], src_tree[Path('src/b.f90')]}, func=mock.ANY)

            # last pass
            mock_run_mp.assert_called_with(items={src_tree[Path('src/root.f90')]}, func=mock.ANY)

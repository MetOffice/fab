##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
from pathlib import Path
import pytest  # type: ignore
from typing import List

from fab.source_tree import \
    SourceVisitor, \
    TreeDescent, \
    TreeVisitor
from fab.artifact import Unknown, New


class TestSourceVisitor(object):
    def test_visit(self, tmp_path: Path):

        seen = []

        def handler(artifact):
            seen.append(artifact)

        test_unit = SourceVisitor(handler)

        first_file = (tmp_path / 'test.foo')
        (tmp_path / 'directory').mkdir()
        second_file = (tmp_path / 'directory' / 'test.bar')

        first_file.write_text("First file")
        second_file.write_text("Second file in directory")

        test_unit.visit(first_file)
        assert seen[0].location == first_file
        assert seen[0].filetype == Unknown
        assert seen[0].state == New

        test_unit.visit(second_file)
        assert seen[1].location == second_file
        assert seen[1].filetype == Unknown
        assert seen[1].state == New


class TestTreeDescent(object):
    @pytest.fixture(scope='class',
                    params=[None, 'nest'])
    def root_dir(self, request):
        yield request.param

    class DummyVisitor(TreeVisitor):
        def __init__(self, outfile: Path):
            self._outfile = outfile
            self.visited: List[Path] = []

        def visit(self, candidate: Path) -> None:
            self.visited.append(candidate)

        @property
        def output(self) -> List[Path]:
            return [self._outfile]

    def test_descent(self, tmp_path: Path, root_dir):
        if root_dir is not None:
            tree_root = tmp_path / root_dir
            tree_root.mkdir()
        else:
            tree_root = tmp_path
        (tree_root / 'alpha').write_text('File in root')
        (tree_root / 'beta').mkdir()
        (tree_root / 'beta' / 'gamma').write_text('File in beta')
        (tree_root / 'beta' / 'delta').write_text('Another file in beta')

        test_unit = TreeDescent(tree_root)
        visitor = self.DummyVisitor(tmp_path / 'foo')
        test_unit.descend(visitor)

        assert visitor.visited == [tree_root / 'beta' / 'gamma',
                                   tree_root / 'beta' / 'delta',
                                   tree_root / 'alpha']

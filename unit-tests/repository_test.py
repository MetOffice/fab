##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Exercise the 'repository' module.
"""
import filecmp
from pathlib import Path
from subprocess import call, Popen
from typing import List, Tuple

from pytest import fixture, raises  # type: ignore
from _pytest.tmpdir import TempPathFactory  # type: ignore

from fab import FabException
from fab.repository import repository_from_url, SubversionRepo


def _tree_compare(first: Path, second: Path) -> None:
    """
    Compare two file trees to ensure they are identical.
    """
    tree_comparison = filecmp.dircmp(str(first), str(second))
    assert len(tree_comparison.left_only) == 0 \
        and len(tree_comparison.right_only) == 0
    _, mismatch, errors = filecmp.cmpfiles(str(first), str(second),
                                           tree_comparison.common_files,
                                           shallow=False)
    assert len(mismatch) == 0 and len(errors) == 0


class TestSubversion:
    """
    Tests of the Subversion repository interface.
    """
    @fixture(scope='class')
    def repo(self, tmp_path_factory: TempPathFactory) -> Tuple[Path, Path]:
        """
        Set up a repository and return its path along with the path of the
        original file tree.
        """
        repo_path = tmp_path_factory.mktemp('repo', numbered=True)
        command = ['svnadmin', 'create', str(repo_path)]
        call(command)
        tree_path = tmp_path_factory.mktemp('tree', numbered=True)
        (tree_path / 'alpha').write_text("First file")
        (tree_path / 'beta').mkdir()
        (tree_path / 'beta' / 'gamma').write_text("Second file")
        command = ['svn', 'import', '-m', "Initial import",
                   str(tree_path), f'file://{repo_path}/trunk']
        call(command)
        return repo_path, tree_path

    def test_extract_from_file(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Subversion
        repository stored on disc.
        """
        test_unit = SubversionRepo(f'file://{repo[0]}/trunk')
        test_unit.extract(tmp_path)
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.svn').exists()

    def test_extract_from_svn(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Subversion
        repository accessed through its own protocol.
        """
        command: List[str] = ['svnserve', '-r', str(repo[0]), '-X']
        process = Popen(command)

        test_unit = SubversionRepo('svn://localhost/trunk')
        test_unit.extract(tmp_path)
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.svn').exists()

        process.wait(timeout=1)
        assert process.returncode == 0

    def test_extract_from_http(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Subversion
        repository accessed through HTTP.

        TODO: This is hard to test without a full Apache installation. For the
              moment we forgo the test on the basis that it's too hard.
        """
        pass


class TestRepoFromURL:
    """
    Tests that a URL can be converted into the correct Repository object.
    """
    @fixture(scope='class',
             params=[
                 {'url': 'svn://example.com/repo',
                  'expect': SubversionRepo},
                 {'url': 'http://example.com/svn',
                  'expect': SubversionRepo},
                 {'url': 'file:///tmp/svn',
                  'expect': SubversionRepo}
             ])
    def cases(self, request):
        """
        Generates a set of test cases.
        """
        yield request.param

    def test_action(self, cases):
        """
        Checks that each URL creates an appropriate Repository object.
        """
        repo = repository_from_url(cases['url'])
        assert isinstance(repo, cases['expect'])
        assert repo.url == cases['url']

    def test_unknown_scheme(self):
        """
        Tests that using a URL with unknown scheme throws an exception.
        """
        with raises(FabException):
            repository_from_url('foo://some/place')

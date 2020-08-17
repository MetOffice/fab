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
from subprocess import run, Popen
import shutil
import signal
import time
from typing import List, Tuple

from pytest import fixture, mark, raises  # type: ignore
from _pytest.tmpdir import TempPathFactory  # type: ignore

from fab import FabException
from fab.repository import repository_from_url, GitRepo, SubversionRepo


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
        assert run(command).returncode == 0
        tree_path = tmp_path_factory.mktemp('tree', numbered=True)
        (tree_path / 'alpha').write_text("First file")
        (tree_path / 'beta').mkdir()
        (tree_path / 'beta' / 'gamma').write_text("Second file")
        command = ['svn', 'import', '-m', "Initial import",
                   str(tree_path), f'file://{repo_path}/trunk']
        assert run(command).returncode == 0
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
        #
        # It seems there can be a delay between the server starting and the
        # listen socket opening. Thus we have a number of retries.
        #
        # TODO: Is there a better solution such that we don't try to connect
        #       until the socket is open?
        #
        for retry in range(3, 0, -1):
            try:
                test_unit.extract(tmp_path)
            except FabException as ex:
                if range == 0:
                    raise ex
                time.sleep(1.0)
            else:
                break
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.svn').exists()

        process.wait(timeout=1)
        assert process.returncode == 0

    @mark.skip(reason="Too hard to test at the moment.")
    def test_extract_from_http(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Subversion
        repository accessed through HTTP.

        TODO: This is hard to test without a full Apache installation. For the
              moment we forgo the test on the basis that it's too hard.
        """
        pass


class TestGit:
    """
    Tests of the Git repository interface.
    """
    @fixture(scope='class')
    def repo(self, tmp_path_factory: TempPathFactory) -> Tuple[Path, Path]:
        """
        Set up a repository and return its path along with the path of the
        original file tree.
        """
        tree_path = tmp_path_factory.mktemp('tree', numbered=True)
        (tree_path / 'alpha').write_text("First file")
        (tree_path / 'beta').mkdir()
        (tree_path / 'beta' / 'gamma').write_text("Second file")

        repo_path = tmp_path_factory.mktemp('repo', numbered=True)
        command = ['git', 'init', str(repo_path)]
        assert run(command).returncode == 0
        #
        # We have to configure this information or the forthcoming commands
        # will fail.
        #
        command = ['git', 'config', 'user.name', 'Testing Tester Tests']
        assert run(command, cwd=str(repo_path)).returncode == 0
        command = ['git', 'config', 'user.email', 'tester@example.com']
        assert run(command, cwd=str(repo_path)).returncode == 0

        for file_object in tree_path.glob('*'):
            if file_object.is_dir():
                shutil.copytree(str(file_object),
                                str(repo_path / file_object.name))
            else:
                shutil.copy(str(file_object),
                            str(repo_path / file_object.name))
        command = ['git', 'add', '-A']
        assert run(command, cwd=str(repo_path)).returncode == 0
        command = ['git', 'commit', '-m', "Initial import"]
        assert run(command, cwd=str(repo_path)).returncode == 0
        return repo_path.absolute(), tree_path.absolute()

    def test_extract_from_file(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Tests that a source tree can be extracted from a local repository.
        """
        test_unit = GitRepo(f'file://{repo[0]}')
        test_unit.extract(tmp_path)
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.git').exists()

    def test_missing_repo(self, tmp_path: Path):
        """
        Tests that an error is returned if the repository is not there.
        """
        fake_repo = tmp_path / "nonsuch.repo"
        fake_repo.mkdir()
        test_unit = GitRepo(f'file://{fake_repo}')
        with raises(FabException) as ex:
            test_unit.extract(tmp_path / 'working')
        expected = "Fault exporting tree from Git repository:"
        assert str(ex.value).startswith(expected)

    @mark.skip(reason="The daemon doesn't seem to be installed.")
    def test_extract_from_git(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Git repository
        accessed through its own protocol.
        """
        command: List[str] = ['git', 'daemon', '--reuseaddr',
                              '--base-path='+str(repo[0].parent),
                              str(repo[0])]
        process = Popen(command)

        test_unit = GitRepo('git://localhost/'+repo[0].name)
        test_unit.extract(tmp_path)
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.git').exists()

        process.send_signal(signal.SIGTERM)
        process.wait(timeout=2)
        assert process.returncode == -15

    @mark.skip(reason="Too hard to test at the moment.")
    def test_extract_from_http(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Git repository
        accessed through HTTP.

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
                 {'access_url': 'git://example.com/git',
                  'repo_class': GitRepo,
                  'repo_url': 'git://example.com/git'},
                 {'access_url': 'git+file:///tmp/git',
                  'repo_class': GitRepo,
                  'repo_url': 'file:///tmp/git'},
                 {'access_url': 'git+git://example.com/git',
                  'repo_class': GitRepo,
                  'repo_url': 'git://example.com/git'},
                 {'access_url': 'git+http://example.com/git',
                  'repo_class': GitRepo,
                  'repo_url': 'http://example.com/git'},
                 {'access_url': 'svn://example.com/svn',
                  'repo_class': SubversionRepo,
                  'repo_url': 'svn://example.com/svn'},
                 {'access_url': 'svn+file:///tmp/svn',
                  'repo_class': SubversionRepo,
                  'repo_url': 'file:///tmp/svn'},
                 {'access_url': 'svn+http://example.com/svn',
                  'repo_class': SubversionRepo,
                  'repo_url': 'http://example.com/svn'},
                 {'access_url': 'svn+svn://example.com/svn',
                  'repo_class': SubversionRepo,
                  'repo_url': 'svn://example.com/svn'},
                 {'access_url': 'file:///tmp/repo',
                  'repo_class': FabException,
                  'exception': "Unrecognised repository scheme: file+file"},
                 {'access_url': 'http://example.com/repo',
                  'repo_class': FabException,
                  'exception': "Unrecognised repository scheme: http+http"},
                 {'access_url': 'foo+file:///tmp/foo',
                  'repo_class': FabException,
                  'exception': "Unrecognised repository scheme: foo+file"}
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
        if issubclass(cases['repo_class'], Exception):
            with raises(cases['repo_class']) as ex:
                _ = repository_from_url(cases['access_url'])
            assert ex.value.args[0] == cases['exception']
        else:
            repo = repository_from_url(cases['access_url'])
            assert isinstance(repo, cases['repo_class'])
            assert repo.url == cases['repo_url']

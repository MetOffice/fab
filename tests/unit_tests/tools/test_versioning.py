##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
Tests version control interfaces.
"""
from filecmp import cmpfiles, dircmp
from pathlib import Path
from shutil import which
from unittest import mock
from subprocess import Popen, run
from time import sleep
from typing import List, Tuple

from pytest import TempPathFactory, fixture, mark, raises

from fab.tools import Category, Fcm, Git, Subversion


class TestGit:
    """
    Tests of the Git repository interface.
    """
    def test_git_constructor(self):
        '''Test the git constructor.'''
        git = Git()
        assert git.category == Category.GIT
        assert git.flags == []

    def test_git_check_available(self):
        '''Check if check_available works as expected.
        '''
        git = Git()
        with mock.patch.object(git, "run", return_value=0):
            assert git.check_available()

        # Now test if run raises an error
        with mock.patch.object(git, "run", side_effect=RuntimeError("")):
            assert not git.check_available()

    def test_git_current_commit(self):
        '''Check current_commit functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned, and stdout of the
        # subprocess run method must be encoded (i.e. decode is called later)
        mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            assert "abc" == git.current_commit()

        tool_run.assert_called_once_with(
            ['git', 'log', '--oneline', '-n', '1'], capture_output=True,
            env=None, cwd='.', check=False)

        # Test if we specify a path
        mock_result = mock.Mock(returncode=0, stdout="abc\ndef".encode())
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            assert "abc" == git.current_commit("/not-exist")

        tool_run.assert_called_once_with(
            ['git', 'log', '--oneline', '-n', '1'], capture_output=True,
            env=None, cwd="/not-exist", check=False)

    def test_git_init(self):
        '''Check init functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            git.init("/src")
        tool_run.assert_called_once_with(
            ['git', 'init', '.'], capture_output=True, env=None,
            cwd='/src', check=False)

    def test_git_clean(self):
        '''Check clean functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            git.clean('/src')
        tool_run.assert_called_once_with(
            ['git', 'clean', '-f'], capture_output=True, env=None,
            cwd='/src', check=False)

    def test_git_fetch(self):
        '''Check getch functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            git.fetch("/src", "/dst", revision="revision")
        tool_run.assert_called_once_with(
            ['git', 'fetch', "/src", "revision"], capture_output=False,
            env=None, cwd='/dst', check=False)

        with mock.patch.object(git, "run",
                               side_effect=RuntimeError("ERR")) as run:
            with raises(RuntimeError) as err:
                git.fetch("/src", "/dst", revision="revision")
            assert "ERR" in str(err.value)
        run.assert_called_once_with(['fetch', "/src", "revision"], cwd="/dst",
                                    capture_output=False)

    def test_git_checkout(self):
        '''Check checkout functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned

        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            git.checkout("/src", "/dst", revision="revision")
        tool_run.assert_any_call(['git', 'fetch', "/src", "revision"],
                                 cwd='/dst', capture_output=False, env=None,
                                 check=False)
        tool_run.assert_called_with(['git', 'checkout', "FETCH_HEAD"],
                                    cwd="/dst", capture_output=False,
                                    env=None, check=False)

        with mock.patch.object(git, "run",
                               side_effect=RuntimeError("ERR")) as run:
            with raises(RuntimeError) as err:
                git.checkout("/src", "/dst", revision="revision")
            assert "ERR" in str(err.value)
        run.assert_called_with(['fetch', "/src", "revision"], cwd="/dst",
                               capture_output=False)

    def test_git_merge(self):
        '''Check merge functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc. '''

        git = Git()
        # Note that only the first line will be returned
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            git.merge("/dst", revision="revision")
        tool_run.assert_called_once_with(
            ['git', 'merge', 'FETCH_HEAD'], capture_output=False,
            env=None, cwd='/dst', check=False)

        # Test the behaviour if merge fails, but merge --abort works:
        # Simple function that raises an exception only the first time
        # it is called.
        def raise_1st_time():
            yield RuntimeError
            yield 0

        with mock.patch.object(git, "run",
                               side_effect=raise_1st_time()) as run:
            with raises(RuntimeError) as err:
                git.merge("/dst", revision="revision")
            assert "Error merging revision. Merge aborted." in str(err.value)
        run.assert_any_call(['merge', "FETCH_HEAD"], cwd="/dst",
                            capture_output=False)
        run.assert_any_call(['merge', "--abort"], cwd="/dst",
                            capture_output=False)

        # Test behaviour if both merge and merge --abort fail
        with mock.patch.object(git, "run",
                               side_effect=RuntimeError("ERR")) as run:
            with raises(RuntimeError) as err:
                git.merge("/dst", revision="revision")
            assert "ERR" in str(err.value)
        run.assert_called_with(['merge', "--abort"], cwd="/dst",
                               capture_output=False)


# ============================================================================
class TestSubversion:
    """
    Tests the Subversion interface.
    """
    def test_svn_constructor(self):
        """
        Test the git constructor.
        """
        svn = Subversion()
        assert svn.category == Category.SUBVERSION
        assert svn.flags == []
        assert svn.name == "Subversion"
        assert svn.exec_name == "svn"

    def test_svn_export(self):
        """
        Ensures an export from repository works.

        Subversion is mocked here to allow testing without the executable.
        Testing with happens below in TestSubversionReal.
        """
        svn = Subversion()
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.export("/src", "/dst", revision="123")

        tool_run.assert_called_once_with(
            ["svn", "export", "--force", "--revision", "123", "/src", "/dst"],
            env=None, cwd=None, capture_output=True, check=False)

        # Test if we don't specify a revision
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.export("/src", "/dst")
        tool_run.assert_called_once_with(
            ["svn", "export", "--force", "/src", "/dst"],
            env=None, cwd=None, capture_output=True, check=False)

    def test_svn_checkout(self):
        '''Check checkout svn functionality. The tests here will actually
        mock the git results, so they will work even if subversion is not
        installed. The system_tests will test an actual check out etc. '''

        svn = Subversion()
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.checkout("/src", "/dst", revision="123")

        tool_run.assert_called_once_with(
            ["svn", "checkout", "--revision", "123", "/src", "/dst"],
            env=None, cwd=None, capture_output=True, check=False)

        # Test if we don't specify a revision
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.checkout("/src", "/dst")
        tool_run.assert_called_once_with(
            ["svn", "checkout", "/src", "/dst"],
            env=None, cwd=None, capture_output=True, check=False)

    def test_svn_update(self):
        '''Check update svn functionality. The tests here will actually
        mock the git results, so they will work even if subversion is not
        installed. The system_tests will test an actual check out etc. '''

        svn = Subversion()
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.update("/dst", revision="123")

        tool_run.assert_called_once_with(
            ["svn", "update", "--revision", "123"],
            env=None, cwd="/dst", capture_output=True, check=False)

    def test_svn_merge(self):
        '''Check merge svn functionality. The tests here will actually
        mock the git results, so they will work even if subversion is not
        installed. The system_tests will test an actual check out etc. '''

        svn = Subversion()
        mock_result = mock.Mock(returncode=0)
        with mock.patch('fab.tools.tool.subprocess.run',
                        return_value=mock_result) as tool_run:
            svn.merge("/src", "/dst", "123")

        tool_run.assert_called_once_with(
            ["svn", "merge", "--non-interactive", "/src@123"],
            env=None, cwd="/dst", capture_output=True, check=False)


def _tree_compare(first: Path, second: Path) -> None:
    """
    Compare two file trees to ensure they are identical.
    """
    tree_comparison = dircmp(str(first), str(second))
    assert len(tree_comparison.left_only) == 0 \
        and len(tree_comparison.right_only) == 0
    _, mismatch, errors = cmpfiles(str(first), str(second),
                                   tree_comparison.common_files,
                                   shallow=False)
    assert len(mismatch) == 0 and len(errors) == 0


@mark.skipif(which('svn') is None,
             reason="No Subversion executable found on path.")
class TestSubversionReal:
    """
    Tests the Subversion interface against a real executable.
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
        test_unit = Subversion()
        test_unit.export(f'file://{repo[0]}/trunk', tmp_path)
        _tree_compare(repo[1], tmp_path)
        assert not (tmp_path / '.svn').exists()

    def test_extract_from_svn(self, repo: Tuple[Path, Path], tmp_path: Path):
        """
        Checks that a source tree can be extracted from a Subversion
        repository accessed through its own protocol.
        """
        command: List[str] = ['svnserve', '-r', str(repo[0]), '-X']
        process = Popen(command)

        test_unit = Subversion()
        #
        # It seems there can be a delay between the server starting and the
        # listen socket opening. Thus we have a number of retries.
        #
        # TODO: Is there a better solution such that we don't try to connect
        #       until the socket is open?
        #
        for retry in range(3, 0, -1):
            try:
                test_unit.export('svn://localhost/trunk', tmp_path)
            except Exception as ex:
                if range == 0:
                    raise ex
                sleep(1.0)
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


# ============================================================================
class TestFcm:
    """
    Tests the FCM interface task.
    """
    def test_fcm_constructor(self):
        """
        Tests this constructor.
        """
        fcm = Fcm()
        assert fcm.category == Category.FCM
        assert fcm.flags == []
        assert fcm.name == "FCM"
        assert fcm.exec_name == "fcm"

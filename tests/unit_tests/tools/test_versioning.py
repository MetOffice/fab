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
from subprocess import Popen, run
from time import sleep
from typing import List, Tuple

from pytest import TempPathFactory, fixture, mark, raises
from pytest_subprocess.fake_process import FakeProcess

from tests.conftest import (ExtendedRecorder,
                            arg_list, call_list, not_found_callback)

from fab.tools.category import Category
from fab.tools.versioning import Fcm, Git, Subversion


class TestGit:
    """
    Tests of the Git repository interface.
    """
    def test_git_constructor(self):
        '''Test the git constructor.'''
        git = Git()
        assert git.category == Category.GIT
        assert git.get_flags() == []

    def test_git_check_available(self, fake_process: FakeProcess) -> None:
        """
        Tests availability check.
        """
        fake_process.register(['git', 'help'], stdout='1.2.3')

        git = Git()
        assert git.check_available()

        fake_process.register(['git', 'help'], callback=not_found_callback)
        assert not git.check_available()

        assert call_list(fake_process) == [
            ['git', 'help'], ['git', 'help']
        ]

    def test_git_current_commit(self, fake_process: FakeProcess) -> None:
        """
        Check current_commit functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        commit_record = fake_process.register(
            ['git', 'log', '--oneline', '-n', '1'], stdout='abc\ndef'
        )
        git = Git()
        assert "abc" == git.current_commit()
        assert call_list(fake_process) == [
            ['git', 'log', '--oneline', '-n', '1']
        ]
        #
        # ToDo: Current directory? Surely this should be an absolute path?
        #       The chances for unexpected behaviour seem too great.
        #
        assert arg_list(commit_record)[0]['cwd'] == '.'

    def test_get_commit(self, fake_process: FakeProcess) -> None:
        """
        Tests commit when specifying a path.
        """
        commit_record = fake_process.register(
            ['git', 'log', '--oneline', '-n', '1'], stdout='abc\ndef'
        )
        git = Git()
        assert "abc" == git.current_commit("/not-exist")
        assert call_list(fake_process) == [
            ['git', 'log', '--oneline', '-n', '1']
        ]
        assert arg_list(commit_record)[0]['cwd'] == '/not-exist'

    def test_git_init(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check init functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        git = Git()
        git.init("/src")
        assert subproc_record.invocations() == [
            ['git', 'init', '.']
        ]
        assert subproc_record.extras()[0]['cwd'] == '/src'

    def test_git_clean(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check clean functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        git = Git()
        git.clean('/src')
        assert subproc_record.invocations() == [
            ['git', 'clean', '-f']
        ]
        assert subproc_record.extras()[0]['cwd'] == '/src'

    def test_git_fetch(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check fetch functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        git = Git()
        git.fetch("/src", "/dst", revision="revision")
        assert subproc_record.invocations() == [
            ['git', 'fetch', "/src", "revision"]
        ]
        assert subproc_record.extras()[0]['cwd'] == '/dst'

    def test_git_fetch_error(self, fake_process: FakeProcess) -> None:
        """
        Tests error causing fetch.
        """
        fetch_record = fake_process.register(
            ['git', 'fetch', '/src', 'revision'], returncode=1
        )
        git = Git()
        with raises(RuntimeError) as err:
            git.fetch("/src", "/dst", revision="revision")
        assert str(err.value).startswith("Command failed with return code 1:")
        assert call_list(fake_process) == [
            ['git', 'fetch', "/src", "revision"]
        ]
        assert arg_list(fetch_record)[0]['cwd'] == '/dst'

    def test_git_checkout(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check checkout functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        git = Git()
        git.checkout("/src", "/dst", revision="revision")
        assert subproc_record.invocations() == [
            ['git', 'fetch', "/src", "revision"],
            ['git', 'checkout', "FETCH_HEAD"]
        ]
        assert subproc_record.extras()[0]['cwd'] == '/dst'
        assert subproc_record.extras()[1]['cwd'] == '/dst'

    def test_git_checkout_error(self, fake_process: FakeProcess) -> None:
        """
        Tests error causing checkout.
        """
        fetch_record = fake_process.register(
            ['git', 'fetch', '/src', 'revision'], returncode=1
        )

        git = Git()
        with raises(RuntimeError) as err:
            git.checkout("/src", "/dst", revision="revision")
        assert str(err.value).startswith("Command failed with return code 1:")
        assert call_list(fake_process) == [
            ['git', 'fetch', "/src", "revision"]
        ]
        assert arg_list(fetch_record)[0]['cwd'] == '/dst'

    def test_git_merge(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check merge functionality. The tests here will actually
        mock the git results, so they will work even if git is not installed.
        The system_tests will test an actual check out etc.
        """
        git = Git()
        git.merge("/dst", revision="revision")
        assert subproc_record.invocations() == [
            ['git', 'merge', 'FETCH_HEAD']
        ]
        assert subproc_record.extras()[0]['cwd'] == '/dst'

    def test_git_merge_error(self, fake_process: FakeProcess) -> None:
        """
        Tests failing merger. This should cause the merge to be rolled back.
        """
        merge_record = fake_process.register(['git', 'merge', 'FETCH_HEAD'],
                                             returncode=1)
        abort_record = fake_process.register(['git', 'merge', '--abort'])

        git = Git()
        with raises(RuntimeError) as err:
            git.merge("/dst", revision="revision")
        assert str(err.value).startswith(
            "Error merging revision. Merge aborted."
        )
        assert call_list(fake_process) == [
            ['git', 'merge', 'FETCH_HEAD'],
            ['git', 'merge', '--abort']
        ]
        assert arg_list(merge_record)[0]['cwd'] == '/dst'
        assert arg_list(abort_record)[0]['cwd'] == '/dst'

    def test_git_merge_collapse(self, fake_process: FakeProcess) -> None:
        """
        Tests failing merge where both merge and abort fail.
        """
        merge_record = fake_process.register(['git', 'merge', 'FETCH_HEAD'],
                                             returncode=1)
        abort_record = fake_process.register(['git', 'merge', '--abort'],
                                             returncode=1)

        git = Git()
        with raises(RuntimeError) as err:
            git.merge("/dst", revision="revision")
        assert str(err.value).startswith("Command failed with return code 1:")
        assert call_list(fake_process) == [
            ['git', 'merge', 'FETCH_HEAD'],
            ['git', 'merge', '--abort']
        ]
        assert arg_list(merge_record)[0]['cwd'] == '/dst'
        assert arg_list(abort_record)[0]['cwd'] == '/dst'


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
        assert svn.get_flags() == []
        assert svn.name == "Subversion"
        assert svn.exec_name == "svn"

    def test_svn_export(self, subproc_record: ExtendedRecorder) -> None:
        """
        Ensures an export from repository works.

        Subversion is mocked here to allow testing without the executable.
        Testing with happens below in TestSubversionReal.
        """
        svn = Subversion()
        #
        # With revision
        #
        svn.export("/src", "/dst", revision="123")
        #
        # Without revision
        #
        svn.export("/src", "/dst")
        assert subproc_record.invocations() == [
            ["svn", "export", "--force", "--revision", "123", "/src", "/dst"],
            ["svn", "export", "--force", "/src", "/dst"]
        ]

    def test_svn_checkout(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check checkout svn functionality. The tests here will actually
        mock the svn results, so they will work even if subversion is not
        installed. The system_tests will test an actual check out etc.
        """
        svn = Subversion()
        #
        # Test with a revision.
        #
        svn.checkout("/src", "/dst", revision="123")
        #
        # Test without a revision.
        #
        svn.checkout("/src", "/dst")
        assert subproc_record.invocations() == [
            ["svn", "checkout", "--revision", "123", "/src", "/dst"],
            ["svn", "checkout", "/src", "/dst"]
        ]

    def test_svn_update(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check update svn functionality. The tests here will actually
        mock the svn results, so they will work even if subversion is not
        installed. The system_tests will test an actual check out etc.
        """
        svn = Subversion()
        svn.update("/dst", revision="123")
        assert subproc_record.invocations() == [
            ["svn", "update", "--revision", "123"]
        ]
        assert subproc_record.extras()[0]['cwd'] == '/dst'

    def test_svn_merge(self, subproc_record: ExtendedRecorder) -> None:
        """
        Check merge svn functionality. The tests here will actually
        mock the subversion results, so they will work even if subversion is
        not installed. The system_tests will test an actual check out etc.
        """
        svn = Subversion()
        svn.merge("/src", "/dst", "123")
        assert subproc_record.invocations() == [
            ["svn", "merge", "--non-interactive", "/src@123"]
        ]
        assert subproc_record.extras()[0]['cwd'] == '/dst'


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
                if retry == 0:
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
        assert fcm.get_flags() == []
        assert fcm.name == "FCM"
        assert fcm.exec_name == "fcm"

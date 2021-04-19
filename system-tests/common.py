##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
"""
System testing for Fab.

Currently runs the tool as a subprocess but should also use it as a library.
"""
from abc import ABC, ABCMeta, abstractmethod
import filecmp
import os.path
from pathlib import Path
import shutil
import subprocess
import sys
from tarfile import TarFile
import os
from typing import Dict, List, Optional, Sequence


class TestParameters(object):
    """
    Holds information about the environment a test is happening in.
    """
    def __init__(self, test_directory: Path, tag: str):
        self._test_dir = test_directory
        self._tag = tag

    @property
    def test_directory(self):
        return self._test_dir

    @property
    def work_directory(self):
        return self._test_dir / 'working'

    @property
    def tag(self):
        return self._tag


class RunCommand(ABC):
    """
    Base class for tests containing useful utility functions.
    """
    def __init__(self,
                 parameters: TestParameters,
                 command: List[str],
                 environment: Dict):
        self._parameters = parameters
        self._command = command
        self._environment = environment
        self._debug_output: Optional[List[str]] = None

        self.return_code: Optional[bool] = None
        self.standard_out: Optional[str] = None
        self.standard_error: Optional[str] = None

    @property
    def test_parameters(self) -> TestParameters:
        return self._parameters

    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError("Abstract methods must be implemented.")

    @property
    def debug_output(self) -> Optional[List[str]]:
        return self._debug_output

    @debug_output.setter
    def debug_output(self, additional_line: str):
        if self._debug_output is None:
            self._debug_output = []
        self._debug_output.append(additional_line)

    def set_up(self):
        """
        Called prior to the run.
        """
        pass

    def execute(self):
        """
        Runs the command and changes state to reflect results.
        """
        thread: subprocess.Popen = subprocess.Popen(self._command,
                                                    env=self._environment,
                                                    stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE)
        stdout: bytes
        stderr: bytes
        stdout, stderr = thread.communicate()
        self.return_code = thread.returncode
        self.standard_out = stdout.decode('utf-8')
        self.standard_error = stderr.decode('utf-8')

        if self.return_code != 0:
            self._debug_output = ['Running command failed:']
            command = ' '.join(self._command)
            self._debug_output.append(f'    command: {command}')
            self._debug_output.append('    stdout: ' + self.standard_out)
            self._debug_output.append('    stderr: ' + self.standard_error)

    def tear_down(self):
        """
        Called following the run.
        """
        pass


class EnterPython(RunCommand, metaclass=ABCMeta):
    """
    Run a Python entry point.
    """
    def __init__(self,
                 tag: str,
                 test_directory: Path,
                 module: str,
                 args: Sequence[str] = (),
                 working_dir=True):
        parameters = TestParameters(test_directory, tag)

        script = f'import sys; import fab.{module}; ' \
                 f'sys.exit(fab.{module}.entry())'
        command = ['python3', '-c', script]
        if working_dir:
            command.extend(['-w', str(parameters.work_directory)])
        command.extend(args)

        system_path = os.environ.get('PATH') or ''
        user_path: List[str] = system_path.split(':')
        try:
            while True:
                user_path.remove('')
        except ValueError:
            pass  # No empty entries to be removed.
        user_path.append(os.path.dirname(sys.executable))

        environment = {'PATH': ':'.join(user_path),
                       'PYTHONPATH': 'source'}

        super().__init__(parameters, command, environment)
        self._working_dir = working_dir


class RunExec(RunCommand):
    """
    Run an executable produced by fab.
    """
    def __init__(self, test_directory: Path):
        parameters = TestParameters(test_directory, 'exec')
        args: List[str] = []
        executable = test_directory / 'working' / 'fab_test'
        command = [str(executable)] + list(args)
        super().__init__(parameters, command, {})

    def description(self) -> str:
        return f"{self.test_parameters.test_directory.stem} - Executing"


class RunFab(EnterPython):
    """
    Run Fab build tool against a source tree.
    """
    def __init__(self,
                 test_directory: Path,
                 target: str,
                 fpp_flags: str = None,
                 fc_flags: str = None,
                 ld_flags: str = None):
        args: List[str] = []

        if fpp_flags:
            # different config file name for fpp flag test
            self.conf_file = test_directory/('stay_config.ini')
        else:
            self.conf_file = test_directory/'config.ini'

        args.append(str(test_directory))
        args.append(str(self.conf_file))

        with open(self.conf_file, 'wt') as configfile:
            configfile.write('[settings] \n'
                             'target = {}\n'
                             'exec-name = fab_test \n'
                             '[flags] \n'.format(target))
            if fpp_flags:
                configfile.write('fpp-flags = {}\n'.format(fpp_flags))
            else:
                configfile.write('fpp-flags = ' + '\n')
            if fc_flags:
                configfile.write('fc-flags = {}\n'.format(fc_flags))
            else:
                configfile.write('fc-flags = ' + '\n')
            if ld_flags:
                configfile.write('ld-flags = {}\n'.format(ld_flags))
            else:
                configfile.write('ld-flags = ' + '\n')
        super().__init__('fab', test_directory, 'builder', args)

    def description(self) -> str:
        return f"{self.test_parameters.test_directory.stem} - Building"

    def set_up(self):
        """
        Ensure there's no working directory left over from previous runs.
        """
        if self.test_parameters.work_directory.is_dir():
            shutil.rmtree(self.test_parameters.work_directory)

    def tear_down(self):
        """
        Clean up config files following the run.
        """
        self.conf_file.unlink()


class RunDump(EnterPython):
    """
    Run Fab dump tool against working directory.
    """
    def __init__(self, test_directory: Path):
        super().__init__('dump', test_directory, 'dumper')

    def description(self) -> str:
        return f"{self.test_parameters.test_directory.stem} - Dumping"

    def teardown(self):
        if self.test_parameters.work_directory.is_dir():
            shutil.rmtree(str(self.test_parameters.work_directory))

    def tear_down(self):
        """
        Tidy up now we're finished with the working directroy.
        """
        shutil.rmtree(self.test_parameters.work_directory)


class RunGrab(EnterPython):
    """
    Run Fab grab tool against a repository.
    """
    def __init__(self, test_directory: Path, repo: str, protocol: str):
        self._scheme = f"{repo}+{protocol}"
        self._repo_path = test_directory.absolute() / "repo"
        self._server: Optional[subprocess.Popen] = None

        if protocol == 'http':
            # TODO: This scheme is included for completeness. Currently there
            #       is no obvious way to test this without an Apache server
            #       which is way too much to consider at the moment.
            # repo_url = f'http://localhost/repo'
            message = "Unable to test Fetch over HTTP protocol."
            raise NotImplementedError(message)

        repo_url = f'{self._scheme}://'
        if protocol == 'file':
            repo_url += f'//{self._repo_path}'
        # HTTP would be included here as well if we were able to test it.
        elif protocol in ['git', 'svn']:
            repo_url += 'localhost/'
        else:
            message = f"Unrecognised URL scheme '{self._scheme}'"
            raise Exception(message)

        super().__init__('grab',
                         test_directory,
                         'grabber',
                         [str(test_directory / 'working'), repo_url],
                         working_dir=False)

    def description(self) -> str:
        name = self.test_parameters.test_directory.stem
        return f"{name} - Grabbing with {self._scheme}"

    def set_up(self):
        if self._repo_path.is_dir():
            shutil.rmtree(self._repo_path)
        archiver = TarFile(self._repo_path.with_suffix('.tar'))
        archiver.extractall(self._repo_path.parent)

        if self.test_parameters.work_directory.is_dir():
            shutil.rmtree(self.test_parameters.work_directory)

        if self._scheme.endswith('+git'):
            # TODO: We would start the daemon here
            raise NotImplementedError("Git protocol not supported")
        elif self._scheme.endswith('+svn'):
            command: List[str] = ['svnserve', '--root', str(self._repo_path),
                                  '-X', '--foreground']
            self._server = subprocess.Popen(command)

    def tear_down(self):
        shutil.rmtree(self.test_parameters.work_directory)

        if self._scheme.endswith('+git'):
            # TODO: We would kill the daemon here
            raise NotImplementedError("Git protocol not supported")
        elif self._scheme.endswith('+svn'):
            self._server.wait(timeout=1)
            if self._server.returncode != 0:
                message = f"Trouble with svnserve: {self._server.stderr}"
                self.debug_output = message

        if self._repo_path.is_dir():
            shutil.rmtree(self._repo_path)


class CheckTask(ABC):
    """
    Abstract parent of all checking test cases.
    """
    def __init__(self, task: RunCommand, name: str):
        self._name = name
        self._task = task

    @property
    def task(self):
        return self._task

    def run(self):
        self._task.set_up()
        self._task.execute()
        #
        # We print this out for debug purposes. If a test fails this output
        # should be visible.
        #
        if self._task.debug_output is not None:
            print('\n'.join(self._task.debug_output))
        self.check()
        self.task.tear_down()

    @abstractmethod
    def check(self):
        raise NotImplementedError("Abstract methods must be implemented.")


class CompareConsoleWithFile(CheckTask):
    """
    Checks console output against expected result.

    The expected result is held in a file "expected.<tag>[.<suffix>].txt.
    Where "tag" comes from the task and "suffix" is specified.
    """
    def __init__(self, task: RunCommand, expectation_suffix=None):
        super().__init__(task, name=task.description())
        leaf_name = f'expected.{task.test_parameters.tag}'
        if expectation_suffix is not None:
            leaf_name = leaf_name + '.' + expectation_suffix
        leaf_name = leaf_name + '.txt'
        path = task.test_parameters.test_directory / leaf_name
        self._expected = path.read_text()

    def check(self):
        assert self.task.return_code == 0
        lines = self.task.standard_out
        assert lines == self._expected


class CompareFileTrees(CheckTask):
    """
    Checks filetree against expected result.

    The test tree is the tasks working directory and the expected result
    is in "expected".
    """
    def __init__(self, task: RunCommand):
        super().__init__(task, name=task.description())
        self._expected = task.test_parameters.test_directory / 'expected'

    def check(self):
        first = self.task.test_parameters.work_directory
        second = self._expected
        tree_comparison = filecmp.dircmp(first, second)
        assert len(tree_comparison.left_only) == 0
        assert len(tree_comparison.right_only) == 0
        _, mismatch, errors = filecmp.cmpfiles(first, second,
                                               tree_comparison.common_files,
                                               shallow=False)
        assert len(mismatch) == 0
        assert len(errors) == 0

##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
System testing for Fab.

Currently runs the tool as a subprocess but should also use it as a library.
'''
import argparse
import datetime
import difflib
import logging
from logging import StreamHandler, FileHandler
import os.path
from pathlib import Path
import shutil
import subprocess
import sys
import os
import traceback
from typing import List, Sequence, Dict

import systest  # type: ignore
from systest import Sequencer


class RunTestCase(systest.TestCase):
    '''
    Base class for tests containing useful utility functions.
    '''

    def run_command_check_output(self,
                                 command: List[str],
                                 environment: Dict,
                                 expected: str):
        '''
        Run ``command`` in the given ``environment`` and then compare
        its stdout to some ``expected`` output, raising an exception
        if either the command fails or the output disagrees.
        '''
        thread: subprocess.Popen = subprocess.Popen(command,
                                                    env=environment,
                                                    stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE)
        stdout: bytes
        stderr: bytes
        stdout, stderr = thread.communicate()
        if thread.returncode != 0:
            print('Running command failed: ', file=sys.stderr)
            print('    command: ' + ' '.join(command), file=sys.stderr)
            print('    stdout: ' + stdout.decode('utf-8'))
            print('    stderr: ' + stderr.decode('utf-8'))

        self.assert_true(thread.returncode == 0)
        self._assert_diff(stdout.decode('utf-8').splitlines(keepends=True),
                          expected)

    @staticmethod
    def _assert_diff(first, second):
        '''
        Raise an exception if ``first`` and ``seconds`` are not the same.

        It is assumed that the arguments are multi-line strings and the
        exception will contain a "diff" dervied from them.
        '''
        if first != second:
            filename, line, _, _ = traceback.extract_stack()[-2]
            differ = difflib.Differ()
            diff = differ.compare(first, second)

            text = ''.join(diff)
            raise systest.TestCaseFailedError(
                '{}:{}: Mismatch found:\n{}'.format(filename,
                                                    line,
                                                    text))


class ExecTestCase(RunTestCase):
    '''
    Test case which expects to run an executable and
    compare its output with an expected result.
    '''

    def __init__(self,
                 test_directory: Path,
                 expectation_file: Path,
                 executable: Path,
                 name: str,
                 args: Sequence[str] = ()):
        super().__init__(name=name)
        self._arguments = args
        self._executable = executable
        self._expected = expectation_file.read_text('utf-8') \
            .splitlines(keepends=True)

    def run(self):
        command = [str(self._executable)] + self._arguments

        self.run_command_check_output(
            command, {}, self._expected)


class PythonTestCase(RunTestCase):
    '''
    Test case which expects to run a Python entry point and
    compare its output with an expected result.
    '''

    def __init__(self,
                 test_directory: Path,
                 working_dir: Path,
                 expectation_file: Path,
                 entry_point: str,
                 name: str,
                 args: Sequence[str] = ()):
        super().__init__(name=name)
        self._test_directory: Path = test_directory
        self._working_dir: Path = working_dir
        self._entry_point = entry_point
        self._arguments = args
        self._expected = expectation_file.read_text('utf-8') \
            .splitlines(keepends=True)

    def run(self):
        script = 'import sys; import fab.entry; ' \
                 f'sys.exit(fab.entry.{self._entry_point}())'
        command = ['python3', '-c', script,
                   '-w', str(self._working_dir)]
        command.extend(self._arguments)

        user_path: List[str] = os.environ.get('PATH').split(':')
        try:
            while True:
                user_path.remove('')
        except ValueError:
            pass  # No empty entries to be removed.
        user_path.append(os.path.dirname(sys.executable))

        environment = {'PATH': ':'.join(user_path),
                       'PYTHONPATH': 'source'}

        self.run_command_check_output(
            command, environment, self._expected)


class CompiledExecTestCase(ExecTestCase):
    '''Run the exec produced by Fab and check its output.'''

    # The result is held in a file 'expected.exec.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.
    #
    def __init__(self,
                 test_directory: Path,
                 expectation_prefix: str = '',):
        args: List[str] = []

        expectation_file = 'expected.exec'
        if expectation_prefix != '':
            expectation_file += '.' + expectation_prefix
        expectation_file += '.txt'

        executable = test_directory / 'working' / 'fab_test'

        super().__init__(test_directory,
                         test_directory / expectation_file,
                         executable,
                         f'{test_directory.stem} - Running Executable',
                         args)


class FabTestCase(PythonTestCase):
    '''Run Fab build tool against source tree and validate result.'''

    # The result is held in a file 'expected.fab.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.
    #
    def __init__(self,
                 test_directory: Path,
                 target: str,
                 expectation_prefix: str = '',
                 fpp_flags: str = None,
                 fc_flags: str = None,
                 ld_flags: str = None):

        args: List[str] = []
        if fpp_flags:
            args.append('--fpp-flags=' + fpp_flags)
        if fc_flags:
            args.append('--fc-flags=' + fc_flags)
        if ld_flags:
            args.append('--ld-flags=' + ld_flags)

        args.extend(['--exec-name', 'fab_test'])
        args.append(target)
        args.append(str(test_directory))

        expectation_file = 'expected.fab'
        if expectation_prefix != '':
            expectation_file += '.' + expectation_prefix
        expectation_file += '.txt'

        super().__init__(test_directory,
                         test_directory / 'working',
                         test_directory / expectation_file,
                         'fab_entry',
                         f'{test_directory.stem} - Running Fab',
                         args)

    def setup(self):
        working_dir: Path = self._test_directory / 'working'
        if working_dir.is_dir():
            shutil.rmtree(str(working_dir))


class DumpTestCase(PythonTestCase):
    '''Run Fab dump tool against working directory and validate result.'''

    # The result is held in a file 'expected.dump.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.
    #
    def __init__(self,
                 test_directory: Path,
                 expectation_prefix: str = ''):

        expectation_file = 'expected.dump'
        if expectation_prefix != '':
            expectation_file += '.' + expectation_prefix
        expectation_file += '.txt'

        super().__init__(test_directory,
                         test_directory / 'working',
                         test_directory / expectation_file,
                         'dump_entry',
                         f'{test_directory.stem} - Running Fab dump',
                         [])

    def teardown(self):
        working_dir: Path = self._test_directory / 'working'
        shutil.rmtree(str(working_dir))


if __name__ == '__main__':
    description = 'Perform Fab system tests'
    cli_parser = argparse.ArgumentParser(description=description,
                                         add_help=False)
    cli_parser.add_argument('-help', '-h', '--help', action='help',
                            help='Display this help message and exit')
    cli_parser.add_argument('-g', '--graph', metavar='FILENAME',
                            nargs='?', const='fab',
                            action='store', type=Path,
                            help='Generate report of test run as graph')
    cli_parser.add_argument('-j', '--json', action='store', metavar='FILENAME',
                            nargs='?', const='fab',
                            type=Path,
                            help='Generate report of test run as JSON')
    cli_parser.add_argument('-l', '--log', action='store', metavar='FILENAME',
                            nargs='?', const='systest', type=Path,
                            help='Generate log file')
    arguments = cli_parser.parse_args()

    # We set up logging by hand rather than calling systest.configure_logging
    # as we want finer control over where things end up. In particular we don't
    # want to generate a log file unless requested.
    #
    logging.getLogger('systest').setLevel(logging.DEBUG)

    stdout_logger: StreamHandler = logging.StreamHandler()
    stdout_logger.setFormatter(systest.ColorFormatter())
    stdout_logger.setLevel(logging.INFO)
    logging.getLogger('systest').addHandler(stdout_logger)

    if arguments.log:
        parent: Path = arguments.log.parent
        if not parent.exists():
            parent.mkdir(parents=True)

        leaf: str = arguments.log.stem
        fmt: str = '%Y_%m_%d_%H_%M_%S.%f'
        timestamp: str = datetime.datetime.now().strftime(fmt)
        leaf += '-' + timestamp
        filename = parent / (leaf + '.log')

        file_logger: FileHandler = logging.FileHandler(filename, 'w')
        fmt = '%(asctime)s %(name)s %(levelname)s %(message)s'
        file_logger.setFormatter(logging.Formatter(fmt))
        stdout_logger.setLevel(logging.DEBUG)
        logging.getLogger('systest').addHandler(file_logger)

    # Tests are performed serially in list order. Where a tuple is found in
    # the list, those tests are run in parallel.
    #
    root_dir = Path(__file__).parent

    # In the sequence structure: Lists are serial while tuples are parallel.
    #
    sequence = (
        [
            FabTestCase(root_dir / 'MinimalFortran', 'test'),
            CompiledExecTestCase(root_dir / 'MinimalFortran'),
            DumpTestCase(root_dir / 'MinimalFortran')
        ],
        [
            FabTestCase(root_dir / 'FortranDependencies', 'first'),
            CompiledExecTestCase(root_dir / 'FortranDependencies'),
            DumpTestCase(root_dir / 'FortranDependencies')
        ],
        [
            [
                FabTestCase(root_dir / 'FortranPreProcess', 'stay_or_go_now',
                            expectation_prefix='stay',
                            fpp_flags='-DSHOULD_I_STAY=yes'),
                CompiledExecTestCase(root_dir / 'FortranPreProcess',
                                     expectation_prefix='stay'),
                DumpTestCase(root_dir / 'FortranPreProcess',
                             expectation_prefix='stay')
            ],
            [
                FabTestCase(root_dir / 'FortranPreProcess', 'stay_or_go_now',
                            expectation_prefix='go'),
                CompiledExecTestCase(root_dir / 'FortranPreProcess',
                                     expectation_prefix='go'),
                DumpTestCase(root_dir / 'FortranPreProcess',
                             expectation_prefix='go')
            ]
        ]
    )

    sequencer: Sequencer = systest.Sequencer('Fab system tests')
    tallies = sequencer.run(sequence)

    summary = sequencer.summary()
    systest.log_lines(summary)

    if arguments.graph:
        sequencer._report_dot(str(arguments.graph))
    if arguments.json:
        sequencer._report_json(str(arguments.json))

    if tallies.failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

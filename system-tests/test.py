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
from typing import List, Sequence

import systest  # type: ignore
from systest import Sequencer


class RunTestCase(systest.TestCase):
    """
    Runs a tool from the fab collection and compares output with expected one.
    """

    def __init__(self,
                 test_directory: Path,
                 working_dir: Path,
                 expectation_file: Path,
                 entry_point: str,
                 args: Sequence[str] = ()):
        super().__init__(name=test_directory.stem)
        self._test_directory: Path = test_directory
        self._working_dir: Path = working_dir
        self._entry_point = entry_point
        self._arguments = args
        self._expected = expectation_file.read_text('utf-8') \
            .splitlines(keepends=True)

    def run(self):
        script = "import sys; import fab.entry; " \
                 f"sys.exit(fab.entry.{self._entry_point}())"
        command = ['python3', '-c', script,
                   '-w', self._working_dir]
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
        thread: subprocess.Popen = subprocess.Popen(command,
                                                    env=environment,
                                                    stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE)
        stdout: bytes
        stderr: bytes
        stdout, stderr = thread.communicate()
        if thread.returncode != 0:
            print('Running Fab failed: ', file=sys.stderr)
            print('    stdout: ' + stdout.decode('utf-8'))
            print('    stderr: ' + stderr.decode('utf-8'))

        self.assert_true(thread.returncode == 0)
        self._assert_diff(stdout.decode('utf-8').splitlines(keepends=True),
                          self._expected)

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


class FabTestCase(RunTestCase):
    """Run Fab build tool against source tree and validate result."""

    # The result is held in a file 'expected.fab.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.
    #
    def __init__(self, test_directory: Path, fpp_flags: str = None):
        args: List[str] = []
        if fpp_flags:
            args.append('--fpp-flags=' + fpp_flags)
        args.append(str(test_directory))
        super().__init__(test_directory,
                         test_directory / 'working',
                         test_directory / 'expected.fab.txt',
                         'fab_entry',
                         args)

    def setup(self):
        working_dir: Path = self._test_directory / 'working'
        if working_dir.is_dir():
            shutil.rmtree(str(working_dir))


class DumpTestCase(RunTestCase):
    """Run Fab dump tool against working directory and validate result."""

    # The result is held in a file 'expected.dump.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.
    #
    def __init__(self, test_directory: Path):
        super().__init__(test_directory,
                         test_directory / 'working',
                         test_directory / 'expected.dump.txt',
                         'dump_entry',
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
            FabTestCase(root_dir / 'MinimalFortran'),
            DumpTestCase(root_dir / 'MinimalFortran')
        ],
        [
            FabTestCase(root_dir / 'FortranDependencies'),
            DumpTestCase(root_dir / 'FortranDependencies')
        ],
        [
            FabTestCase(root_dir / 'FortranPreProcess',
                        fpp_flags='-DSHOULD_I_STAY=yes'),
            DumpTestCase(root_dir / 'FortranPreProcess')
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

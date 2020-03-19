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
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import systest  # type: ignore
from systest import Sequencer


class FabTestCase(systest.TestCase):
    '''Run Fab against source tree and validate result.'''
    # The result is held in a file 'expected.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.

    def __init__(self, test_directory: Path, fpp_flags: str = None):
        super().__init__(name=test_directory.stem)
        self._test_directory: Path = test_directory
        self._fpp_flags = fpp_flags

        expectation_file = test_directory / 'expected.txt'
        self._expected = expectation_file.read_text('utf-8') \
            .splitlines(keepends=True)

    def setup(self):
        working_dir: Path = self._test_directory / 'working'
        if working_dir.is_dir():
            shutil.rmtree(str(working_dir))

    def teardown(self):
        working_dir: Path = self._test_directory / 'working'
        shutil.rmtree(str(working_dir))

    def run(self):
        command = ['python3', '-m', 'fab']
        if self._fpp_flags is not None:
            command.append("--fpp-flags=" + self._fpp_flags)
        command.append(self._test_directory)

        environment = {'PYTHONPATH': 'source'}
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

    def _assert_diff(self, first, second):
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

    sequence = [
        FabTestCase(root_dir / 'MinimalFortran'),
        FabTestCase(root_dir / 'FortranDependencies'),
        FabTestCase(root_dir / 'FortranPreProcess',
                    fpp_flags='-DSHOULD_I_STAY=yes')
        ]

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

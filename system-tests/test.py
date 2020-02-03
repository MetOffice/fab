##############################################################################
# (c) Crown copyright Met Office. All rights reserved.
# For further details please refer to the file COPYRIGHT
# which you should have received as part of this distribution
##############################################################################
'''
System testing for Fab.

Currently runs the tool as a subprocess but should also use it as a library.
'''
import difflib
from pathlib import Path
import subprocess
import traceback
from typing import Generator

import systest


class FabTestCase(systest.TestCase):
    '''Run Fab against source tree and validate result.'''
    #  The result is held in a file 'expected.txt' in the test directory.
    #
    # This comment exists as the framework hijacks the docstring for output.

    def __init__(self, test_directory: Path):
        super().__init__(name=test_directory.stem)
        self._test_directory = test_directory

        expectation_file = test_directory / 'expected.txt'
        self._expected = expectation_file.read_text('utf-8') \
            .splitlines(keepends=True)

    def run(self):
        command = ['fab', self._test_directory]
        stdout: bytes = subprocess.check_output(command)
        self._assert_diff(self._expected,
                          stdout.decode('utf8').splitlines(keepends=True))

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
    root_dir = Path(__file__).parent

    # Tests are performed serially in list order. Where a tuple is found in
    # the list, those tests are run in parallel.
    #
    sequence = [
        FabTestCase(root_dir / 'MinimalFortran')
        ]

    systest.configure_logging()
    sequencer = systest.Sequencer('Fab system tests')
    sequencer.run(sequence)
    sequencer.report()

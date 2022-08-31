from unittest import mock
from unittest.mock import call

from fab.build_config import BuildConfig
from fab.constants import COMPILED_FILES, BUILD_OUTPUT
from fab.steps.archive_objects import ArchiveObjects


class Test_archive_objects(object):

    def test_for_exes(self):
        # as used when archiving before linking exes
        ar = ArchiveObjects()
        config = BuildConfig('proj')
        targets = ['prog1', 'prog2']

        artefact_store = {COMPILED_FILES: {target: [f'{target}.o', 'util.o'] for target in targets}}

        with mock.patch('fab.steps.archive_objects.run_command') as mock_run_command:
            ar.run(artefact_store=artefact_store, config=config)

        # todo: replace with new property when available
        expect_output_fpaths = []

        expect_output_fpaths = [
            str(config.project_workspace / BUILD_OUTPUT / 'prog1.a'),
            str(config.project_workspace / BUILD_OUTPUT / 'prog2.a'),
        ]

        expected_calls = [call() for prog in progs]

        mock_run_command.assert_has_calls([
            call('ar', 'cr', ),
        ])

        assert artefact_store[foo] = foo

    def test_for_library(self):
        # as used when building an object archive or archiving before linking a shared library
        artefact_store = {COMPILED_FILES: {
            None: ['util1.o', 'util2.o'],
        }}

        mock_run_command.assert_called_once_with([
            'ar', 'cr',
        ])

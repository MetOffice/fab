from unittest import mock
from unittest.mock import call

from fab.build_config import BuildConfig
from fab.constants import BUILD_OUTPUT, OBJECT_FILES, OBJECT_ARCHIVES
from fab.steps.archive_objects import ArchiveObjects


class Test_archive_objects(object):

    def test_for_exes(self):
        # as used when archiving before linking exes
        ar = ArchiveObjects()
        config = BuildConfig('proj')

        targets = ['prog1', 'prog2']
        artefact_store = {OBJECT_FILES: {target: [f'{target}.o', 'util.o'] for target in targets}}

        with mock.patch('fab.steps.archive_objects.run_command') as mock_run_command:
            ar.run(artefact_store=artefact_store, config=config)

        # ensure the correct command line calls were made
        expected_calls = [
            call(['ar', 'cr', str(config.build_output / f'{target}.a'), f'{target}.o', 'util.o'])
            for target in targets
        ]
        mock_run_command.assert_has_calls(expected_calls)

        # ensure the correct artefacts were created
        assert artefact_store[OBJECT_ARCHIVES] == {
            target: [str(config.build_output / f'{target}.a')] for target in targets}

    def test_for_library(self):
        # as used when building an object archive or archiving before linking a shared library
        pass

        config = BuildConfig('proj')
        ar = ArchiveObjects(output_fpath=config.build_output / 'mylib.a')

        artefact_store = {OBJECT_FILES: {None: ['util1.o', 'util2.o']}}

        with mock.patch('fab.steps.archive_objects.run_command') as mock_run_command:
            ar.run(artefact_store=artefact_store, config=config)

        # ensure the correct command line calls were made
        mock_run_command.assert_called_once_with([
            'ar', 'cr', str(config.build_output / f'mylib.a'), f'util1.o', 'util2.o'])

        # ensure the correct artefacts were created
        assert artefact_store[OBJECT_ARCHIVES] == {
            None: [str(config.build_output / 'mylib.a')]}

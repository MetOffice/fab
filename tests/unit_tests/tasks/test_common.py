"""
Test test_common.py.

"""
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from fab.steps.archive_objects import ArchiveObjects
from fab.steps.link_exe import LinkExe


class TestLinkExe(object):
    def test_run(self):
        # ensure the command is formed correctly, with the flags at the end (why?!)
        linker = LinkExe(linker='foolink', flags=['-fooflag', '-barflag'], output_fpath='foo.exe')

        with mock.patch('fab.steps.link_exe.run_command') as mock_run:
            linker.run(
                artefact_store={'compiled_fortran': [Mock(output_fpath='foo.o'), Mock(output_fpath='bar.o')]},
                config=mock.Mock(workspace=Path('workspace')))

        mock_run.assert_called_with(['foolink', '-o', 'foo.exe', 'foo.o', 'bar.o', '-fooflag', '-barflag'])


class TestArchiveObjects(object):
    def test_run(self):
        # ensure the command is formed correctly, with the output filename before the contents
        archiver = ArchiveObjects(archiver='fooarc', output_fpath='$output/foo.a')

        with mock.patch('fab.steps.archive_objects.run_command') as mock_run:
            artefact_store = {'compiled_fortran': [Mock(output_fpath='foo.o'), Mock(output_fpath='bar.o')]}
            archiver.run(artefact_store=artefact_store, config=mock.Mock(workspace=Path('workspace')))

        mock_run.assert_called_with(['fooarc', 'cr', 'workspace/build_output/foo.a', 'foo.o', 'bar.o'])

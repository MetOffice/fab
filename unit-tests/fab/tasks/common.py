"""
Test common.py.

"""
from unittest import mock
from unittest.mock import Mock

from fab.tasks.common import LinkExe, CreateObjectArchive


class TestLinkExe(object):
    def test_run(self):
        # ensure the command is formed correctly, with the flags at the end (why?!)
        linker = LinkExe(linker='foolink', flags=['-fooflag', '-barflag'], output_fpath='foo.exe')

        with mock.patch('fab.tasks.common.run_command') as mock_run:
            linker.run(compiled_files=[Mock(output_fpath='foo.o'), Mock(output_fpath='bar.o')])

        mock_run.assert_called_with(['foolink', '-o', 'foo.exe', 'foo.o', 'bar.o', '-fooflag', '-barflag'])

class TestCreateObjectArchive(object):
    def test_run(self):
        # ensure the command is formed correctly, with the output filename before the contents
        archiver = CreateObjectArchive(archiver='fooarc', output_fpath='foo.a')

        with mock.patch('fab.tasks.common.run_command') as mock_run:
            archiver.run(compiled_files=[Mock(output_fpath='foo.o'), Mock(output_fpath='bar.o')])

        mock_run.assert_called_with(['fooarc', 'cr', 'foo.a', 'foo.o', 'bar.o'])

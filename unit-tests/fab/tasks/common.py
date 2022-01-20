"""
Test common.py.

"""
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, DEFAULT

from fab.tasks.common import LinkExe, CreateObjectArchive, PreProcessor


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


class TestPreProcessor(object):

    def test_f90(self):
        self._fortran_common(suffix='.f90')

    def test_F90(self):
        self._fortran_common(suffix='.F90')

    def _fortran_common(self, suffix):
        # ensure the command is formed correctly for fortran files
        mock_flags = Mock()
        mock_flags.flags_for_path.return_value = ['-fooflag', '-barflag']
        pp = PreProcessor(preprocessor='foopp', flags=mock_flags, workspace=Path("workspace"), output_suffix='.foo')

        input_file = Path(f'workspace/build_source/foo/bar{suffix}')

        with mock.patch('fab.tasks.common.run_command') as mock_run:
            pp.run(fpath=input_file)

        mock_run.assert_called_with([
            'foopp', '-fooflag', '-barflag',
            str(input_file), 'workspace/build_output/foo/bar.f90'])

    def test_c(self):
        # ensure the command is formed correctly for c files, and that the pragma injector is called
        mock_flags = Mock()
        mock_flags.flags_for_path.return_value = ['-fooflag', '-barflag']
        pp = PreProcessor(preprocessor='foopp', flags=mock_flags, workspace=Path("workspace"), output_suffix='.foo')

        with mock.patch('pathlib.Path.open'):
            with mock.patch.multiple('fab.tasks.common', _CTextReaderPragmas=DEFAULT, run_command=DEFAULT) as mocks:
                pp.run(fpath=Path('workspace/build_source/foo/bar.c'))

        mocks['_CTextReaderPragmas'].assert_called_with(Path('workspace/build_source/foo/bar.c'))
        mocks['run_command'].assert_called_with([
            'foopp', '-fooflag', '-barflag',
            'workspace/build_source/foo/bar.c.prag', 'workspace/build_output/foo/bar.c'])

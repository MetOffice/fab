import logging
import zlib
from pathlib import Path
from unittest import mock

from fab.util import file_walk

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder, GrabPreBuild
from fab.steps.link_exe import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.walk_source import FindSourceFiles


class TestFortranPrebuild(object):

    def build_config(self, fab_workspace, prebuild_folder=None):
        logging.getLogger('fab').setLevel(logging.WARNING)

        build_config = BuildConfig(
            project_label='test_prebuild',
            fab_workspace=fab_workspace,
            steps=[
                GrabFolder(Path(__file__).parent / 'project-source', dst='src'),
                # insert a prebuild grab step or don't insert anything
                *([GrabPreBuild(prebuild_folder)] if prebuild_folder else []),
                FindSourceFiles(),
                fortran_preprocessor(preprocessor='cpp -traditional-cpp -P'),
                Analyse(root_symbol='my_prog'),
                CompileFortran(compiler='gfortran -c', common_flags=['-J', '$output']),
                LinkExe(flags=['-lgfortran']),
            ],
            multiprocessing=False,
        )

        return build_config

    def test_reliable_hashes(self, tmp_path):
        # Make sure we get the SAME MODULE HASHES in DIFFERENT FOLDERS.
        # This is achieved by changing to the source file's folder during compilation.
        # If we don't do this, then modules built in different workspaces can have different folders embedded in them,
        # thereby changing their hash, thereby changing the hash of things which depend on them...
        # build the project in "some other fab workspace", from where we'll share its prebuild

        config1 = self.build_config(fab_workspace=tmp_path / 'workspace_one')
        config1.run()

        files1 = set(file_walk(config1.build_output))
        hashes1 = {f.relative_to(config1.build_output): zlib.crc32(open(f, 'rb').read()) for f in files1}

        config2 = self.build_config(fab_workspace=tmp_path / 'workspace_two')
        config2.run()

        files2 = set(file_walk(config2.build_output))
        hashes2 = {f.relative_to(config2.build_output): zlib.crc32(open(f, 'rb').read()) for f in files2}

        del hashes1[Path('__analysis.csv')]
        del hashes2[Path('__analysis.csv')]
        assert hashes1 == hashes2

    def test_vanilla_prebuild(self, tmp_path):
        # share a prebuild from a different folder

        # build the project in "some other fab workspace", from where we'll share its prebuild
        other_config = self.build_config(fab_workspace=tmp_path / 'other_workspace')
        other_config.run()

        # now build the project in our workspace.
        my_config = self.build_config(fab_workspace=tmp_path / 'my_workspace',
                                      prebuild_folder=other_config.prebuild_folder)

        with mock.patch('fab.steps.compile_fortran.CompileFortran.compile_file') as mock_compile_file:
            my_config.run()

        # make sure we didn't call the compiler
        mock_compile_file.assert_not_called()

        # make sure the exe was built
        exe = my_config.project_workspace / 'my_prog.exe'
        assert exe.exists()

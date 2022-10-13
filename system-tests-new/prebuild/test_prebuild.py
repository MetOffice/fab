import logging
import zlib
from pathlib import Path
from unittest import mock

from fab.build_config import BuildConfig
from fab.steps.analyse import Analyse
from fab.steps.compile_fortran import CompileFortran
from fab.steps.grab import GrabFolder, GrabPreBuild
from fab.steps.link import LinkExe
from fab.steps.preprocess import fortran_preprocessor
from fab.util import file_walk
from fab.steps.find_source_files import FindSourceFiles


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
                CompileFortran(compiler='gfortran -c'),
                LinkExe(flags=['-lgfortran']),
            ],
            multiprocessing=False,
        )

        return build_config

    def test_repeatable_fmod_hashes(self, tmp_path):
        # Make sure we get the SAME FORTRAN MODULE HASHES in DIFFERENT FOLDERS.
        # This is achieved by changing to the source file's folder during compilation.
        # If we don't do this, then modules built in different workspaces can have different folders embedded in them,
        # thereby changing their hash, thereby changing the hash of things which depend on them.
        # Build the project in "some other fab workspace", from where we'll share its prebuild

        # This test also checks that the object files are identical,
        # and that the prebuild filenames are the same.

        config1 = self.build_config(fab_workspace=tmp_path / 'workspace_one')
        config1.run()

        pb_files1 = set(file_walk(config1.prebuild_folder))
        pb_hashes1 = {f.relative_to(config1.build_output): zlib.crc32(open(f, 'rb').read()) for f in pb_files1}

        config2 = self.build_config(fab_workspace=tmp_path / 'workspace_two')
        config2.run()

        pb_files2 = set(file_walk(config2.prebuild_folder))
        pb_hashes2 = {f.relative_to(config2.build_output): zlib.crc32(open(f, 'rb').read()) for f in pb_files2}

        # Discount the analysis results, which  will have different contents because they include the source folder,
        # which changes between workspaces, but that doesn't cause a problem.
        pb_hashes1 = {p: h for p, h in pb_hashes1.items() if p.suffix != '.an'}
        pb_hashes2 = {p: h for p, h in pb_hashes2.items() if p.suffix != '.an'}

        # Make sure the remaining prebuild file contents are the same in both workspaces.
        assert pb_hashes1 == pb_hashes2

        # check the filenames are the same
        pb1_fnames = {p.name for p in pb_files1}
        pb2_fnames = {p.name for p in pb_files2}
        assert pb1_fnames == pb2_fnames

    def test_vanilla_prebuild(self, tmp_path):
        # share a prebuild from a different folder
        compile_file = 'fab.steps.compile_fortran.CompileFortran.compile_file'
        parse_fortran = 'fab.tasks.fortran.FortranAnalyser._parse_file'

        # build the project in "some other fab workspace", from where we'll share its prebuild
        other_config = self.build_config(fab_workspace=tmp_path / 'other_workspace')
        other_config.run()

        # now build the project in our workspace.
        my_config = self.build_config(fab_workspace=tmp_path / 'my_workspace',
                                      prebuild_folder=other_config.prebuild_folder)
        with mock.patch(parse_fortran) as mock_parse_fortran:
            with mock.patch(compile_file) as mock_compile_file:
                my_config.run()

        # make sure we didn't call the analyser
        mock_parse_fortran.assert_not_called()

        # make sure we didn't call the compiler
        mock_compile_file.assert_not_called()

        # make sure the exe was built
        exe = my_config.project_workspace / 'my_prog.exe'
        assert exe.exists()

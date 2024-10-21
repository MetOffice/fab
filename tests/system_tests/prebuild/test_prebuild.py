import logging
import os
import zlib
from pathlib import Path
from unittest import mock

from fab.build_config import BuildConfig
from fab.steps.analyse import analyse
from fab.steps.compile_fortran import compile_fortran
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.grab.prebuild import grab_pre_build
from fab.steps.link import link_exe
from fab.steps.preprocess import preprocess_fortran
from fab.tools import ToolBox
from fab.util import file_walk


@mock.patch.dict(os.environ)
class TestFortranPrebuild(object):

    def build_config(self, fab_workspace, grab_prebuild_folder=None):
        # remove FFLAGS from the *mocked*, i.e copy of, the environment variables
        if os.getenv('FFLAGS'):
            del os.environ['FFLAGS']

        logging.getLogger('fab').setLevel(logging.WARNING)

        with BuildConfig(
                project_label='test_prebuild', tool_box=ToolBox(),
                fab_workspace=fab_workspace, multiprocessing=False) as config:
            grab_folder(config, Path(__file__).parent / 'project-source',
                        dst_label='src')
            # insert a prebuild grab step or don't insert anything
            if grab_prebuild_folder:
                grab_pre_build(config, grab_prebuild_folder)
            find_source_files(config)
            preprocess_fortran(config)
            analyse(config, root_symbol='my_prog')
            compile_fortran(config)
            link_exe(config, flags=['-lgfortran'])

        return config

    def test_repeatable_fmod_hashes(self, tmp_path):
        # Make sure we get the SAME FORTRAN MODULE HASHES in DIFFERENT FOLDERS.
        # This is achieved by changing to the source file's folder during compilation.
        # If we don't do this, then modules built in different workspaces can have different folders embedded in them,
        # thereby changing their hash, thereby changing the hash of things which depend on them.
        # Build the project in "some other fab workspace", from where we'll share its prebuild

        # This test also checks that the object files are identical,
        # and that the prebuild filenames are the same.

        config1 = self.build_config(fab_workspace=tmp_path / 'first_workspace')
        pb_files1 = set(file_walk(config1.prebuild_folder))
        pb_hashes1 = {f.relative_to(config1.build_output): zlib.crc32(open(f, 'rb').read()) for f in pb_files1}

        config2 = self.build_config(fab_workspace=tmp_path / 'second_workspace')
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

        # build the project in "some other fab workspace", from where we'll share its prebuild
        first_project = self.build_config(fab_workspace=tmp_path / 'first_workspace')

        # now build the project in our workspace.
        with mock.patch('fab.parse.fortran.FortranAnalyser._parse_file') as mock_parse_fortran:
            with mock.patch('fab.steps.compile_fortran.compile_file') as mock_compile_file:
                second_project = self.build_config(fab_workspace=tmp_path / 'second_workspace',
                                                   grab_prebuild_folder=first_project.prebuild_folder)

        # make sure we didn't call the analyser or compiler
        mock_parse_fortran.assert_not_called()
        mock_compile_file.assert_not_called()

        # make sure the exe was built
        exe = second_project.project_workspace / 'my_prog'
        assert exe.exists()

        # make sure the prebuild files are the same
        first_prebuilds = {p.name for p in (file_walk(first_project.prebuild_folder))}
        second_prebuilds = {p.name for p in (file_walk(second_project.prebuild_folder))}
        assert first_prebuilds == second_prebuilds
        for fname in first_prebuilds | second_prebuilds:
            assert files_identical(first_project.prebuild_folder / fname,
                                   second_project.prebuild_folder / fname)

    def test_deleted_original(self, tmp_path):
        # Ensure we compile the files in our source folder and not those specified in analysis prebuilds.
        # (We could have copied the analysis prebuilds from another user/location).
        # We do this by deleting the source folder from the first build.
        # We also delete the compiler prebuilds to get the compiler to run a second time.
        first_project = self.build_config(fab_workspace=tmp_path / 'first_workspace')

        # Delete the original source that was analysed and compiled.
        # This is not the source folder, it's the preprocessing results in the build output.
        os.remove(first_project.build_output / 'src/my_mod.f90')
        os.remove(first_project.build_output / 'src/my_prog.f90')
        (first_project.build_output / 'src').rmdir()

        # Delete the compiler prebuilds to make the compiler run again.
        for f in file_walk(first_project.prebuild_folder):
            if f.suffix in ['.o', ',mod']:
                os.remove(f)

        # This should now recompile but not reanalyse.
        # If we don't "fixup" the analysis results paths as we load them,
        # then the compiler will try to compile the original, deleted source.
        # If this runs, the test passes.
        self.build_config(fab_workspace=tmp_path / 'second_workspace',
                          grab_prebuild_folder=first_project.prebuild_folder)


def files_identical(a, b):
    a_bytes = open(a, 'rb').read()
    b_bytes = open(b, 'rb').read()
    return a_bytes == b_bytes

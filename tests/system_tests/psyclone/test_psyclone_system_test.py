# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import filecmp
import shutil
from os import unlink
from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import BuildConfig
from fab.parse.x90 import X90Analyser, AnalysedX90
from fab.steps.cleanup_prebuilds import cleanup_prebuilds
from fab.steps.find_source_files import find_source_files
from fab.steps.grab.folder import grab_folder
from fab.steps.preprocess import preprocess_fortran
from fab.steps.psyclone import _analysis_for_prebuilds, make_parsable_x90, preprocess_x90, psyclone, tool_available
from fab.util import file_checksum

SAMPLE_KERNEL = Path(__file__).parent / 'kernel.f90'

# this x90 has "name=" keywords and is not parsable fortran
SAMPLE_X90 = Path(__file__).parent / 'algorithm.x90'

# this is the sanitised version, with the name keywords removed, so it is parsable fortran
EXPECT_PARSABLE_X90 = Path(__file__).parent / 'expect.parsable_x90'

# the name keywords which are removed from the x90
NAME_KEYWORDS = ['name a', 'name b', 'name c', 'name d', 'name e', 'name f']


# todo: Tidy up the test data in here. There are two sample projects, one not even in its own subfolder.
#       Make the skeleton sample call more than one kernel.
#       Make the skeleton sample include a big X90 and a little x90.


def test_make_parsable_x90(tmp_path):
    # turn x90 into parsable fortran by removing the name keyword from calls to invoke
    grab_x90_path = SAMPLE_X90
    input_x90_path = tmp_path / grab_x90_path.name
    shutil.copy(grab_x90_path, input_x90_path)

    parsable_x90_path = make_parsable_x90(input_x90_path)

    x90_analyser = X90Analyser()
    with BuildConfig('proj', fab_workspace=tmp_path) as config:
        x90_analyser._config = config  # todo: code smell
        x90_analyser.run(parsable_x90_path)

    # ensure the files are as expected
    assert filecmp.cmp(parsable_x90_path, EXPECT_PARSABLE_X90)

    # make_parsable_x90() puts its output file next to the source.
    # Because we're reading sample code from our Fab git repos,
    # we don't want to leave this test output in our working copies, so delete it.
    # Otherwise, it'll appear in the output from `git status`.
    unlink(parsable_x90_path)


class TestX90Analyser(object):

    expected_analysis_result = AnalysedX90(
        fpath=EXPECT_PARSABLE_X90,
        file_hash=3906123776,
        kernel_deps={'kernel_one_type', 'kernel_two_type'})

    def run(self, tmp_path):
        parsable_x90_path = self.expected_analysis_result.fpath
        x90_analyser = X90Analyser()
        with BuildConfig('proj', fab_workspace=tmp_path) as config:
            x90_analyser._config = config
            analysed_x90, _ = x90_analyser.run(parsable_x90_path)  # type: ignore
            # don't delete the prebuild
            cleanup_prebuilds(config, n_versions=999)

        return analysed_x90

    def test_vanilla(self, tmp_path):
        analysed_x90 = self.run(tmp_path)
        assert analysed_x90 == self.expected_analysis_result

    def test_prebuild(self, tmp_path):
        self.run(tmp_path)

        # Run it a second time, ensure it's not re-processed and still gives the correct result
        with mock.patch('fab.parse.x90.X90Analyser.walk_nodes') as mock_walk:
            analysed_x90 = self.run(tmp_path)
        mock_walk.assert_not_called()
        assert analysed_x90 == self.expected_analysis_result


class Test_analysis_for_prebuilds(object):

    def test_analyse(self, tmp_path):

        with BuildConfig('proj', fab_workspace=tmp_path) as config:
            transformation_script_hash, analysed_x90, all_kernel_hashes = \
                _analysis_for_prebuilds(config,
                                        x90s=[SAMPLE_X90],
                                        kernel_roots=[Path(__file__).parent],
                                        # the script is just hashed, so any one will do - use this file!
                                        transformation_script=Path(__file__))

        # transformation_script_hash
        assert transformation_script_hash == file_checksum(__file__).file_hash

        # analysed_x90
        assert analysed_x90 == {
            SAMPLE_X90: AnalysedX90(
                fpath=SAMPLE_X90.with_suffix('.parsable_x90'),
                file_hash=file_checksum(SAMPLE_X90).file_hash,
                kernel_deps={'kernel_one_type', 'kernel_two_type'})}

        # all_kernel_hashes
        assert all_kernel_hashes == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
            'kernel_three_type': 319981435,
            'kernel_four_type': 1427207736,
        }


@pytest.mark.skipif(not tool_available(), reason="psyclone cli tool not available")
class TestPsyclone(object):
    """
    Basic run of the psyclone step.

    """
    @pytest.fixture
    def config(self, tmp_path):
        config = BuildConfig('proj', fab_workspace=tmp_path, multiprocessing=False)
        return config

    def steps(self, config):
        here = Path(__file__).parent
        grab_folder(config, here / 'skeleton')
        find_source_files(config)
        preprocess_fortran(config, common_flags=['-P'])

        preprocess_x90(config)
        # todo: it's easy to forget that we need to find the f90 not the F90.
        #       it manifests as an error, a missing kernel hash.
        #       Perhaps add validation, warn if it's not in the build_output folder?
        psyclone(config, kernel_roots=[
            config.build_output / 'kernel',
            # this second folder is just to test the multiple folders code, which was bugged. There's no kernels there.
            Path(__file__).parent / 'skeleton/algorithm',
        ])

    def test_run(self, config):
        # if these files exist after the run then we know:
        #   a) the expected files were created
        #   b) the prebuilds were protected from automatic cleanup
        expect_prebuild_files = [
            # Expect these prebuild files
            # The kernel hash differs between fpp and cpp, so just use wildcards.
            'algorithm_mod.*.an',  # x90 analysis result
            'my_kernel_mod.*.an',  # kernel analysis results
            'algorithm_mod.*.f90',  # prebuild
            'algorithm_mod_psy.*.f90',  # prebuild
        ]

        expect_build_files = [
            # there should be an f90 and a _psy.f90 built from the x90
            'algorithm/algorithm_mod.f90',
            'algorithm/algorithm_mod_psy.f90',
        ]

        # Glob returns a generator, which can't simply be tested if it's empty.
        # So use a list instead:
        assert all(list(config.prebuild_folder.glob(f)) == [] for f in expect_prebuild_files)
        assert all(list(config.build_output.glob(f)) == [] for f in expect_build_files)
        with config, pytest.warns(UserWarning, match="no transformation script specified"):
            self.steps(config)
        assert all(list(config.prebuild_folder.glob(f)) != [] for f in expect_prebuild_files)
        assert all(list(config.build_output.glob(f)) != [] for f in expect_build_files)

    def test_prebuild(self, tmp_path, config):
        with config, pytest.warns(UserWarning, match="no transformation script specified"):
            self.steps(config)

        # make sure no work gets done the second time round
        with mock.patch('fab.parse.x90.X90Analyser.walk_nodes') as mock_x90_walk:
            with mock.patch('fab.parse.fortran.FortranAnalyser.walk_nodes') as mock_fortran_walk:
                with mock.patch('fab.steps.psyclone.run_psyclone') as mock_run:
                    with config, pytest.warns(UserWarning, match="no transformation script specified"):
                        self.steps(config)

        mock_x90_walk.assert_not_called()
        mock_fortran_walk.assert_not_called()
        mock_run.assert_not_called()

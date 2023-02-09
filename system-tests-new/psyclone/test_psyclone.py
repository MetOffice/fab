# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import filecmp
import shutil
from os import unlink
from pathlib import Path
from typing import Tuple
from unittest import mock

import pytest

from fab.build_config import BuildConfig
from fab.parse.x90 import X90Analyser, AnalysedX90
from fab.steps.find_source_files import FindSourceFiles
from fab.steps.grab.folder import GrabFolder
from fab.steps.preprocess import fortran_preprocessor
from fab.steps.psyclone import make_parsable_x90, Psyclone, psyclone_preprocessor

SAMPLE_KERNEL = Path(__file__).parent / 'kernel.f90'

# this x90 has "name=" keywords and is not parsable fortran
SAMPLE_X90 = Path(__file__).parent / 'algorithm.x90'

# this is the sanitised version, with the name keywords removed, so it is parsable fortran
EXPECT_PARSABLE_X90 = Path(__file__).parent / 'expect.parsable_x90'

# the name keywords which are removed from the x90
NAME_KEYWORDS = ['name a', 'name b', 'name c', 'name d', 'name e', 'name f']


def test_make_parsable_x90(tmp_path):
    # turn x90 into parsable fortran by removing the name keyword from calls to invoke
    grab_x90_path = SAMPLE_X90
    input_x90_path = tmp_path / grab_x90_path.name
    shutil.copy(grab_x90_path, input_x90_path)

    parsable_x90_path, removed_names = make_parsable_x90(input_x90_path)

    # the point of this function is to make the file parsable by fparser
    x90_analyser = X90Analyser()
    x90_analyser._config = BuildConfig('proj', fab_workspace=tmp_path)
    x90_analyser._config._prep_output_folders()
    x90_analyser.run(parsable_x90_path)

    # ensure the files are as expected
    assert removed_names == NAME_KEYWORDS
    assert filecmp.cmp(parsable_x90_path, EXPECT_PARSABLE_X90)

    # don't leave this in my git repo
    unlink(parsable_x90_path)


class TestX90Analyser(object):

    expected_analysis_result = AnalysedX90(
        fpath=EXPECT_PARSABLE_X90,
        file_hash=3906123776,
        kernel_deps={'kernel_one_type', 'kernel_two_type'})

    def run(self, tmp_path) -> Tuple[AnalysedX90, Path]:
        parsable_x90_path = self.expected_analysis_result.fpath
        x90_analyser = X90Analyser()
        x90_analyser._config = BuildConfig('proj', fab_workspace=tmp_path)
        x90_analyser._config._prep_output_folders()
        return x90_analyser.run(parsable_x90_path)  # type: ignore

    def test_vanilla(self, tmp_path):
        analysed_x90, _ = self.run(tmp_path)
        assert analysed_x90 == self.expected_analysis_result

    def test_prebuild(self, tmp_path):
        self.run(tmp_path)

        # Run it a second time, ensure it's not re-processed and still gives the correct result
        with mock.patch('fab.parse.x90.X90Analyser.walk_nodes') as mock_walk:
            analysed_x90, _ = self.run(tmp_path)
        mock_walk.assert_not_called()
        assert analysed_x90 == self.expected_analysis_result


class Test_analysis(object):

    @pytest.fixture
    def psyclone_step(self, tmp_path) -> Psyclone:
        psyclone_step = Psyclone(kernel_roots=[Path(__file__).parent])
        psyclone_step._config = BuildConfig('proj', fab_workspace=tmp_path)
        psyclone_step._config._prep_output_folders()
        return psyclone_step

    def test_analyse(self, psyclone_step):

        artefact_store = {'preprocessed_x90': [SAMPLE_X90]}
        mp_payload = psyclone_step.analysis_for_prebuilds(artefact_store=artefact_store)

        assert mp_payload.used_kernel_hashes == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
        }

    def test_analyse_kernels(self, psyclone_step):
        kernel_files = [SAMPLE_KERNEL]

        all_kernels = psyclone_step._analyse_kernels(kernel_files=kernel_files)

        assert all_kernels == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
            'kernel_three_type': 319981435,
            'kernel_four_type': 1427207736,
        }


class TestPsyclone(object):
    """
    Basic run of the psyclone step.

    """
    def test_run(self, tmp_path):
        here = Path(__file__).parent

        config = BuildConfig('proj', fab_workspace=tmp_path, verbose=True)

        config.steps = [
            GrabFolder(here / 'skeleton'),
            FindSourceFiles(),
            fortran_preprocessor(preprocessor='fpp -P'),

            psyclone_preprocessor(),
            # todo: it's easy to forget that we need to find the f90 not the F90.
            #       it manifests as an error, a missing kernel hash.
            #       Perhaps add validation, warn if it's not in the build_output folder?
            Psyclone(kernel_roots=[config.build_output / 'kernel']),
        ]

        # if these files exist after the run then know:
        #   a) the expected files were created
        #   b) the prebuilds were protected from automatic cleanup
        expect_files = [
            # there should be an f90 and a _psy.f90 built from the x90
            config.build_output / 'algorithm/algorithm_mod.parsable_x90',
            config.build_output / 'algorithm/algorithm_mod.f90',
            config.build_output / 'algorithm/algorithm_mod_psy.f90',

            # Expect these prebuild files
            config.prebuild_folder / 'algorithm_mod.205866748.an',  # x90 analysis result
            config.prebuild_folder / 'kernel_mod.4076575089.an',  # kernel analysis results
            config.prebuild_folder / 'algorithm_mod.4366459448.f90',  # prebuild
            config.prebuild_folder / 'algorithm_mod_psy.4366459448.f90',  # prebuild
        ]

        assert all(not f.exists() for f in expect_files)
        config.run()
        assert all(f.exists() for f in expect_files)

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
from fab.parse.fortran.x90 import X90Analyser, AnalysedX90
from fab.steps.psyclone import make_parsable_x90, Psyclone


SAMPLE_KERNEL = Path(__file__).parent / 'sample_kernel.f90'

# this x90 has "name=" keywords and is not parsable fortran
SAMPLE_X90 = Path(__file__).parent / 'sample.x90'

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
        file_hash=3649068569,
        kernel_deps={
            'kernel_one_type': 'imaginary_mod_one',
            'kernel_two_type': 'imaginary_mod_one',
        })

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
        with mock.patch('fab.parse.fortran.x90.X90Analyser.walk_nodes') as mock_walk:
            analysed_x90, _ = self.run(tmp_path)
        mock_walk.assert_not_called()
        assert analysed_x90 == self.expected_analysis_result


class TestPsyclone(object):

    @pytest.fixture
    def psyclone_step(self, tmp_path):
        psyclone_step = Psyclone(kernel_roots=[Path(__file__).parent])
        psyclone_step._config = BuildConfig('proj', fab_workspace=tmp_path)
        psyclone_step._config._prep_output_folders()

        return psyclone_step

    def test_analyse(self, psyclone_step):

        artefact_store = {'preprocessed_x90': [SAMPLE_X90]}
        psyclone_step.analyse(artefact_store=artefact_store)

        assert psyclone_step._used_kernel_hashes == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
        }

        # todo: better testing of the logic which joins the kernel names into used_kernels

    def test_analyse_kernels(self, psyclone_step):
        kernel_files = [SAMPLE_KERNEL]

        all_kernels = psyclone_step._analyse_kernels(kernel_files=kernel_files)

        assert all_kernels == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
            'kernel_three_type': 319981435,
            'kernel_four_type': 1427207736,
        }

    def test_gen_prebuild_hash(self):
        # todo
        pass


# todo: test putting the analysis step before and after psyclone

# todo: test cleanup of prebuild files for:
#       - analysed x90
#       - analysed kernels (should work with no code, it's the same analyser)
#       - psyclone output
#       - general analysis both before and afterwards

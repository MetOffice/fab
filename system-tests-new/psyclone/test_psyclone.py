# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import filecmp
import shutil
from pathlib import Path
from unittest import mock

import pytest

from fab.build_config import BuildConfig
from fab.parse.fortran.x90 import X90Analyser, AnalysedX90
from fab.steps.psyclone import make_parsable_x90, Psyclone


SAMPLE_KERNEL = Path(__file__).parent / 'sample_kernel.f90'

# this x90 has "name=" keywords and is not parsable fortran
SAMPLE_X90 = Path(__file__).parent / 'sample.x90'

# this is the sanitised version, with the name keywords removed, so it is parsable fortran
PARSABLE_X90 = Path(__file__).parent / 'sample.parsable_x90'

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
    x90_analyser._prebuild_folder = tmp_path
    x90_analyser.run(parsable_x90_path)

    # ensure the files are as expected
    assert removed_names == NAME_KEYWORDS
    assert filecmp.cmp(parsable_x90_path, PARSABLE_X90)


class TestX90Analyser(object):

    expected_analysis_result = AnalysedX90(
        fpath=PARSABLE_X90,
        file_hash=3739281332,
        kernel_deps={
            'kernel_type_one': 'imaginary_mod_one',
            'kernel_type_two': 'imaginary_mod_one',
            'kernel_type_three': 'imaginary_mod_one',
            'kernel_type_four': 'imaginary_mod_two',
            'kernel_type_five': 'imaginary_mod_two',
            'kernel_type_six': 'imaginary_mod_two',
        })

    def run(self, tmp_path) -> AnalysedX90:
        parsable_x90_path = self.expected_analysis_result.fpath
        x90_analyser = X90Analyser()
        x90_analyser._prebuild_folder = tmp_path
        return x90_analyser.run(parsable_x90_path)

    def test_vanilla(self, tmp_path):
        analysed_x90 = self.run(tmp_path)
        assert analysed_x90 == self.expected_analysis_result

    def test_prebuild(self, tmp_path):
        self.run(tmp_path)

        # Run it a second time, ensure it's not re-processed and still gives the correct result
        with mock.patch('fab.parse.fortran.x90.X90Analyser.walk_nodes') as mock_walk:
            analysed_x90 = self.run(tmp_path)
        mock_walk.assert_not_called()
        assert analysed_x90 == self.expected_analysis_result


class TestPsyclone(object):

    @pytest.fixture
    def common(self, tmp_path):
        config = BuildConfig('proj', fab_workspace=tmp_path)
        config.prebuild_folder.mkdir(parents=True, exist_ok=False)

        psyclone_step = Psyclone(kernel_roots=[Path(__file__).parent])
        psyclone_step._config = config

        return config, psyclone_step

    def test_analyse(self, common):
        config, psyclone_step = common

        artefact_store = {'preprocessed_x90': [SAMPLE_X90]}
        psyclone_step.analyse(artefact_store=artefact_store)

        assert psyclone_step._used_kernel_hashes == {
            'kernel_one_type': 2915127408,
            'kernel_two_type': 3793991362,
            'kernel_three_type': 319981435,
            'kernel_four_type': 1427207736,
            'kernel_five_type': 3893954241,
            'kernel_six_type': 1691832228,
        }

        # todo: better testing of the logic which joins the kernel names into used_kernels

    def test_analyse_kernels(self, common):
        config, psyclone_step = common
        kernel_files = [SAMPLE_KERNEL]

        all_kernels = psyclone_step._analyse_kernels(kernel_files=kernel_files)

        assert all_kernels == {'kernel_one_type': 2915127408, 'kernel_two_type': 3793991362}

    def test_gen_prebuild_hash(self):
        pass


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
from fab.steps.psyclone import make_compliant_x90, Psyclone


def test_make_compliant_x90(tmp_path):
    # make non-compliant x90 parsable by removing the name keyword from calls to invoke
    grab_x90_path = Path(__file__).parent / 'sample.non_compliant_x90'
    input_x90_path = tmp_path / grab_x90_path.name
    shutil.copy(grab_x90_path, input_x90_path)

    compliant_x90_path, removed_names = make_compliant_x90(input_x90_path)

    assert removed_names == ['name a', 'name b', 'name c', 'name d', 'name e', 'name f']
    assert filecmp.cmp(compliant_x90_path, Path(__file__).parent / 'sample.compliant_x90')


class TestX90Analyser(object):

    expected_analysis_result = AnalysedX90(
        fpath=Path(__file__).parent / 'sample.compliant_x90',
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
        compliant_x90_path = self.expected_analysis_result.fpath
        x90_analyser = X90Analyser()
        x90_analyser._prebuild_folder = tmp_path
        return x90_analyser.run(compliant_x90_path)

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


@pytest.fixture
def common(tmp_path):
    config = BuildConfig('proj', fab_workspace=tmp_path)
    config.prebuild_folder.mkdir(parents=True, exist_ok=False)

    psyclone_step = Psyclone()
    psyclone_step._config = config

    return config, psyclone_step


class Test_analyse_kernels(object):
    # The psyclone step runs the normal fortran analyser on all kernel files,
    # with an extra node handler injected, for detecting and hashing kernel metadata.
    # The standard fortran analysis should be unaffected, including identical prebuilds,
    # plus we should get back a hash of all the *used* kernels.

    def test_vanilla(self, common):
        config, psyclone_step = common
        kernel_files = [Path(__file__).parent / 'sample_kernel.f90']

        all_kernels = psyclone_step._analyse_kernels(kernel_files=kernel_files)

        assert all_kernels == {'kernel_one_type': 2915127408, 'kernel_two_type': 3793991362}


class Test_analyse(object):

    def test_analyse(self, common):
        config, psyclone_step = common

        # artefact_store = {'preprocessed_x90': []}
        mp_results = [
            (Path('foo'), [''])
        ]
        with mock.patch('fab.steps.psyclone.Psyclone.run_mp', return_value=mp_results)
            psyclone_step.analyse(artefact_store=None)

        used_kernels = ['kernel_two_type']


        assert psyclone_step._used_kernel_hashes == {}

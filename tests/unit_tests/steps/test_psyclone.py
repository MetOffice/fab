# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Tuple

import pytest

from fab.build_config import BuildConfig
from fab.parse.x90 import AnalysedX90
from fab.steps.psyclone import MpPayload, Psyclone


class Test_gen_prebuild_hash(object):
    """
    Tests for the prebuild hashing calculation.

    """
    @pytest.fixture
    def data(self, tmp_path) -> Tuple[Psyclone, MpPayload, Path, int]:
        config = BuildConfig('proj', fab_workspace=tmp_path)
        config._prep_output_folders()

        psyclone_step = Psyclone(kernel_roots=[Path(__file__).parent])
        psyclone_step._config = config

        mp_payload = MpPayload()
        mp_payload.transformation_script_hash = 123

        x90_file = Path('foo.x90')
        mp_payload.analysed_x90 = {
            x90_file: AnalysedX90(
                fpath=x90_file,
                file_hash=234,
                kernel_deps={'kernel1', 'kernel2'})
        }

        mp_payload.all_kernel_hashes = {
            'kernel1': 345,
            'kernel2': 456,
        }

        expect_hash = 223133615

        return psyclone_step, mp_payload, x90_file, expect_hash

    def test_vanilla(self, data):
        psyclone_step, mp_payload, x90_file, expect_hash = data
        result = psyclone_step._gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash

    def test_file_hash(self, data):
        # changing the file hash should change the hash
        psyclone_step, mp_payload, x90_file, expect_hash = data
        mp_payload.analysed_x90[x90_file]._file_hash += 1
        result = psyclone_step._gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_kernal_deps(self, data):
        # changing a kernel deps hash should change the hash
        psyclone_step, mp_payload, x90_file, expect_hash = data
        mp_payload.all_kernel_hashes['kernel1'] += 1
        result = psyclone_step._gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_trans_script(self, data):
        # changing the transformation script should change the hash
        psyclone_step, mp_payload, x90_file, expect_hash = data
        mp_payload.transformation_script_hash += 1
        result = psyclone_step._gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_cli_args(self, data):
        # changing the cli args should change the hash
        psyclone_step, mp_payload, x90_file, expect_hash = data
        psyclone_step.cli_args = ['--foo']
        result = psyclone_step._gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result != expect_hash

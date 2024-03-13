# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Tuple
from unittest import mock

import pytest

from fab.parse.x90 import AnalysedX90
from fab.steps.psyclone import _check_override, _gen_prebuild_hash, MpCommonArgs


class Test_gen_prebuild_hash(object):
    """
    Tests for the prebuild hashing calculation.

    """
    @pytest.fixture
    def data(self, tmp_path) -> Tuple[MpCommonArgs, Path, int]:

        x90_file = Path('foo.x90')
        analysed_x90 = {
            x90_file: AnalysedX90(
                fpath=x90_file,
                file_hash=234,
                kernel_deps={'kernel1', 'kernel2'})
        }

        all_kernel_hashes = {
            'kernel1': 345,
            'kernel2': 456,
        }

        expect_hash = 223133615

        mp_payload = MpCommonArgs(
            analysed_x90=analysed_x90,
            all_kernel_hashes=all_kernel_hashes,
            transformation_script_hash=123,
            cli_args=[],
            config=None, kernel_roots=None, transformation_script=None,  # type: ignore[arg-type]
            overrides_folder=None, override_files=None,  # type: ignore[arg-type]
        )
        return mp_payload, x90_file, expect_hash

    def test_vanilla(self, data):
        mp_payload, x90_file, expect_hash = data
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash

    def test_file_hash(self, data):
        # changing the file hash should change the hash
        mp_payload, x90_file, expect_hash = data
        mp_payload.analysed_x90[x90_file]._file_hash += 1
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_kernal_deps(self, data):
        # changing a kernel deps hash should change the hash
        mp_payload, x90_file, expect_hash = data
        mp_payload.all_kernel_hashes['kernel1'] += 1
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_trans_script(self, data):
        # changing the transformation script should change the hash
        mp_payload, x90_file, expect_hash = data
        mp_payload.transformation_script_hash += 1
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == expect_hash + 1

    def test_cli_args(self, data):
        # changing the cli args should change the hash
        mp_payload, x90_file, expect_hash = data
        mp_payload.cli_args = ['--foo']
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result != expect_hash


class Test_check_override(object):

    def test_no_override(self):
        mp_payload = mock.Mock(overrides_folder=Path('/foo'), override_files=[Path('/foo/bar.f90')])

        check_path = Path('/not_foo/bar.f90')
        result = _check_override(check_path=check_path, mp_payload=mp_payload)
        assert result == check_path

    def test_override(self):
        mp_payload = mock.Mock(overrides_folder=Path('/foo'), override_files=[Path('/foo/bar.f90')])

        check_path = Path('/foo/bar.f90')
        result = _check_override(check_path=check_path, mp_payload=mp_payload)
        assert result == mp_payload.overrides_folder / 'bar.f90'

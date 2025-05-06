# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path
from typing import Tuple
from unittest.mock import Mock

from pytest import fixture, warns
from pytest_subprocess.fake_process import FakeProcess

from fab.parse.x90 import AnalysedX90
from fab.steps.psyclone import _check_override, _gen_prebuild_hash, MpCommonArgs
from fab.util import string_checksum


class TestGenPrebuildHash:
    """
    Tests for the prebuild hashing calculation.

    """
    @fixture(scope='function')
    def data(self, tmp_path) -> Tuple[MpCommonArgs, Path]:

        x90_file = Path('foo.x90')
        analysed_x90 = {
            x90_file: AnalysedX90(
                fpath=x90_file,
                file_hash=234,
                kernel_deps={'kernel1', 'kernel2'}
            )
        }

        all_kernel_hashes = {
            'kernel1': 345,
            'kernel2': 456,
        }

        # the script is just hashed later, so any one will do
        transformation_script = tmp_path / 'transformation.py'
        transformation_script.write_text("#!/usr/bin/env python\n")

        mp_payload = MpCommonArgs(
            analysed_x90=analysed_x90,
            all_kernel_hashes=all_kernel_hashes,
            cli_args=[],
            config=None,  # type: ignore[arg-type]
            kernel_roots=[],
            transformation_script=lambda x, y: transformation_script,
            api='lfric',
            overrides_folder=None,
            override_files=None,  # type: ignore[arg-type]
        )
        return mp_payload, x90_file

    def test_vanilla(self, data):
        """
        Tests computation of hash.

        ToDo: Monkeying with "private" members.
        """
        mp_payload, x90_file,  = data
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == 5699416685

    def test_file_hash(self, data):
        """
        Tests changing source file changes hash.

        ToDo: Monkeying with "private" members.
        """
        mp_payload, x90_file = data
        mp_payload.analysed_x90[x90_file]._file_hash += 1
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == 5699416686

    def test_kernal_deps(self, data) -> None:
        """
        Tests changing a kernel changes hash.

        ToDo: Monkeying with "private" members.
        """
        mp_payload, x90_file = data
        mp_payload.all_kernel_hashes['kernel1'] -= 1
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == 5699416684

    def test_trans_script(self, data) -> None:
        """
        Tests change of transformation script changes hash.

        ToDo: Monkeying with "private" members.
        """
        mp_payload, x90_file = data
        mp_payload.transformation_script = None
        with warns(UserWarning, match="no transformation script specified"):
            result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result == 3232323824

    def test_api(self, data, fake_process: FakeProcess) -> None:
        """
        Tests API change causes hash change.

        ToDo: Monkeying with "private" members.
        """
        mp_payload, x90_file = data

        old_hash = string_checksum(mp_payload.api)
        # Change the API by appending "_new"
        mp_payload.api = mp_payload.api + "_new"
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        # transformation_script_hash = 0
        new_hash = string_checksum(mp_payload.api)
        # Make sure we really changed the
        assert new_hash != old_hash
        assert result == 6037862461

    def test_cli_args(self, data):
        # changing the cli args should change the hash
        mp_payload, x90_file = data
        mp_payload.cli_args = ['--foo']
        result = _gen_prebuild_hash(x90_file=x90_file, mp_payload=mp_payload)
        assert result != 123


class TestCheckOverride:
    """
    Tests overriding.

    ToDo: Monkeying with "private" members.
    """
    def test_no_override(self):
        """
        Tests straioght operation with no override.
        """
        mp_payload = Mock(overrides_folder=Path('/foo'),
                          override_files=[Path('/foo/bar.f90')])

        check_path = Path('/not_foo/bar.f90')
        result = _check_override(check_path=check_path, mp_payload=mp_payload)
        assert result == check_path

    def test_override(self):
        """
        Tests operation with override.
        """
        mp_payload = Mock(overrides_folder=Path('/foo'),
                          override_files=[Path('/foo/bar.f90')])

        check_path = Path('/foo/bar.f90')
        result = _check_override(check_path=check_path, mp_payload=mp_payload)
        assert result == mp_payload.overrides_folder / 'bar.f90'

# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import copy
from pathlib import Path

import pytest
from fab.parse.x90 import AnalysedX90


class TestAnalysedX90(object):

    @pytest.fixture
    def analysed_x90(self):
        return AnalysedX90(
            fpath=Path('foo.f90'), file_hash=123,
            kernel_deps={'kernel_one_type', 'kernel_two_type'})

    @pytest.fixture
    def different_kernel_deps(self):
        return AnalysedX90(
            fpath=Path('foo.f90'), file_hash=123,
            kernel_deps={'kernel_three_type', 'kernel_four_type'})

    @pytest.fixture
    def as_dict(self):
        return {
            'fpath': 'foo.f90',
            'file_hash': 123,
            'kernel_deps': ['kernel_one_type', 'kernel_two_type'],
        }

    def test_to_dict(self, analysed_x90, as_dict):
        assert analysed_x90.to_dict() == as_dict

    def test_from_dict(self, analysed_x90, as_dict):
        assert AnalysedX90.from_dict(as_dict) == analysed_x90

    def test_save_load(self, analysed_x90, tmp_path):
        fpath = tmp_path / 'analysed_x90.an'

        analysed_x90.save(fpath)
        loaded = AnalysedX90.load(fpath)

        assert loaded == analysed_x90

    # eq
    def test_eq(self, analysed_x90):
        assert analysed_x90 == copy.deepcopy(analysed_x90)

    def test_eq_different_kernel_deps(self, analysed_x90, different_kernel_deps):
        assert analysed_x90 != different_kernel_deps

    # hash
    def test_hash(self, analysed_x90):
        assert hash(analysed_x90) == hash(copy.deepcopy(analysed_x90))

    def test_hash_different_kernel_deps(self, analysed_x90, different_kernel_deps):
        assert hash(analysed_x90) != hash(different_kernel_deps)

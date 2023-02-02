# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
import copy
from pathlib import Path

import pytest

from fab.parse.fortran import AnalysedFortran


class TestAnalysedFortran(object):

    @pytest.fixture
    def analysed_fortran(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_fpath(self):
        return AnalysedFortran(
            fpath=Path('bar.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_file_hash(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=456,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_module_defs(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod3'],
            symbol_defs=['my_mod3', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_symbol_defs(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func3', 'my_func4'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_module_deps(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod3'],
            symbol_deps=['other_mod3', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_symbol_deps(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func3', 'other_func4'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_mo_commented_file_deps(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['other_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_file_deps(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods2.f90')],
            psyclone_kernels={'kernel_one_type': 123, 'kernel_two_type': 456}
        )

    @pytest.fixture
    def different_psyclone_kernels(self):
        return AnalysedFortran(
            fpath=Path('foo.f90'), file_hash=123,
            module_defs=['my_mod1', 'my_mod2'],
            symbol_defs=['my_mod1', 'my_mod2', 'my_func1', 'my_func2'],
            module_deps=['other_mod1', 'other_mod2'],
            symbol_deps=['other_mod1', 'other_mod2', 'other_func1', 'other_func2'],
            mo_commented_file_deps=['my_file.c'], file_deps=[Path('other_mods.f90')],
            psyclone_kernels={'kernel_three_type': 789}
        )

    @pytest.fixture
    def as_dict(self):
        return {
            'fpath': 'foo.f90',
            'file_hash': 123,
            'module_defs': ['my_mod1', 'my_mod2'],
            'symbol_defs': ['my_func1', 'my_func2', 'my_mod1', 'my_mod2'],
            'module_deps': ['other_mod1', 'other_mod2'],
            'symbol_deps': ['other_func1', 'other_func2', 'other_mod1', 'other_mod2'],
            'mo_commented_file_deps': ['my_file.c'],
            'file_deps': ['other_mods.f90'],
            'psyclone_kernels': {'kernel_one_type': 123, 'kernel_two_type': 456},
        }

    def test_add_module_def(self, analysed_fortran):
        analysed_fortran.add_module_def('my_mod3')
        assert analysed_fortran.module_defs == {'my_mod1', 'my_mod2', 'my_mod3'}
        assert analysed_fortran.symbol_defs == {'my_func1', 'my_func2', 'my_mod1', 'my_mod2', 'my_mod3'}

    def test_add_module_dep(self, analysed_fortran):
        analysed_fortran.add_module_dep('other_mod3')
        assert analysed_fortran.module_deps == {'other_mod1', 'other_mod2', 'other_mod3'}
        assert analysed_fortran.symbol_deps == {'other_func1', 'other_func2', 'other_mod1', 'other_mod2', 'other_mod3'}

    def test_mod_filenames(self, analysed_fortran):
        assert analysed_fortran.mod_filenames == {'my_mod1.mod', 'my_mod2.mod'}

    def test_to_dict(self, analysed_fortran, as_dict):
        assert analysed_fortran.to_dict() == as_dict

    def test_from_dict(self, analysed_fortran, as_dict):
        assert AnalysedFortran.from_dict(as_dict) == analysed_fortran

    def test_save_load(self, analysed_fortran, tmp_path):
        fpath = tmp_path / 'analysed_fortran.an'

        analysed_fortran.save(fpath)
        loaded = AnalysedFortran.load(fpath)

        assert loaded == analysed_fortran

    def test_eq(self, analysed_fortran):
        assert analysed_fortran == copy.deepcopy(analysed_fortran)

    def test_eq_different_module_defs(self, analysed_fortran, different_module_defs):
        assert analysed_fortran != different_module_defs

    def test_eq_different_module_deps(self, analysed_fortran, different_module_deps):
        assert analysed_fortran != different_module_deps

    def test_eq_different_mo_commented_file_deps(self, analysed_fortran, different_mo_commented_file_deps):
        assert analysed_fortran != different_mo_commented_file_deps

    def test_eq_different_psyclone_kernels(self, analysed_fortran, different_psyclone_kernels):
        assert analysed_fortran != different_psyclone_kernels

    # We can't record the return value from self.hash() because it's different each time we invoke Python.
    def test_hash(self, analysed_fortran):
        assert hash(analysed_fortran) == hash(copy.deepcopy(analysed_fortran))

    def test_hash_different_module_defs(self, analysed_fortran, different_module_defs):
        assert hash(analysed_fortran) != hash(different_module_defs)

    def test_hash_different_module_deps(self, analysed_fortran, different_module_deps):
        assert hash(analysed_fortran) != hash(different_module_deps)

    def test_hash_different_mo_commented_file_deps(self, analysed_fortran, different_mo_commented_file_deps):
        assert hash(analysed_fortran) != hash(different_mo_commented_file_deps)

    def test_hash_different_psyclone_kernels(self, analysed_fortran, different_psyclone_kernels):
        assert hash(analysed_fortran) != hash(different_psyclone_kernels)


# to/from dict should use vars(), and just be in the base class


# hash should use field_names() and just be in the base class

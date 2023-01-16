# ##############################################################################
#  (c) Crown copyright Met Office. All rights reserved.
#  For further details please refer to the file COPYRIGHT
#  which you should have received as part of this distribution
# ##############################################################################
from pathlib import Path

import pytest
from fab.parse.c import AnalysedC


class TestAnalysedC(object):

    @pytest.fixture
    def analysed_c(self):
        return AnalysedC(
            fpath=Path('foo.f90'), file_hash=123,
            symbol_defs={'my_func1', 'my_func2'},
            symbol_deps={'other_func1', 'other_func2'},
            file_deps={Path('other_file1.f90'), Path('other_file1.f90')},
        )

    def test_save_load(self, analysed_c, tmp_path):
        fpath = tmp_path / 'analysed_c.an'

        analysed_c.save(fpath)
        loaded = AnalysedC.load(fpath)

        assert loaded == analysed_c

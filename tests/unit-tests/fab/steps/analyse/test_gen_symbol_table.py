from pathlib import Path, PosixPath

import pytest

from fab.dep_tree import AnalysedFile

from fab.steps.analyse import Analyse


@pytest.fixture
def analysed_files():
    return {Path("foo.c"): AnalysedFile(fpath=Path('foo.c'), symbol_defs=['foo_1', 'foo_2'], file_hash=None),
            Path("bar.c"): AnalysedFile(fpath=Path('bar.c'), symbol_defs=['bar_1', 'bar_2'], file_hash=None)}


class Test_gen_symbol_table(object):

    def test_vanilla(self, analysed_files):
        
        analyser = Analyse()

        result = analyser._gen_symbol_table(all_analysed_files=analysed_files)

        assert result == {
            'foo_1': PosixPath('foo.c'),
            'foo_2': PosixPath('foo.c'),
            'bar_1': PosixPath('bar.c'),
            'bar_2': PosixPath('bar.c'),
        }

    def test_duplicate_symbol(self, analysed_files):
        analysed_files[Path("bar.c")].symbol_defs.append('foo_1')

        analyser = Analyse()

        with pytest.warns(UserWarning):
            result = analyser._gen_symbol_table(all_analysed_files=analysed_files)

        assert result == {
            'foo_1': PosixPath('foo.c'),
            'foo_2': PosixPath('foo.c'),
            'bar_1': PosixPath('bar.c'),
            'bar_2': PosixPath('bar.c'),
        }

    def test_special_measures(self, analysed_files):

        analyser = Analyse()
        analyser.special_measure_analysis_results = analysed_files.values()

        result = analyser._gen_symbol_table(all_analysed_files=dict())

        assert result == {
            'foo_1': PosixPath('foo.c'),
            'foo_2': PosixPath('foo.c'),
            'bar_1': PosixPath('bar.c'),
            'bar_2': PosixPath('bar.c'),
        }


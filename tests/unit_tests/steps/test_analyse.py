from pathlib import Path

import pytest

from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse


class Test_analyse_source_code(object):
    xxx


class Test_analyse_dependencies(object):
    xxx


class Test__get_latest_checksums(object):
    xxx


class Test__load_analysis_results(object):
    xxx


class Test__parse_files(object):
    xxx


class Test__gen_file_deps(object):
    xxx


class Test_gen_symbol_table(object):

    @pytest.fixture
    def analysed_files(self):
        return [AnalysedFile(fpath=Path('foo.c'), symbol_defs=['foo_1', 'foo_2'], file_hash=None),
                AnalysedFile(fpath=Path('bar.c'), symbol_defs=['bar_1', 'bar_2'], file_hash=None)]

    def test_vanilla(self, analysed_files):
        analyser = Analyse(root_symbol=None)

        result = analyser._gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }

    def test_duplicate_symbol(self, analysed_files):
        # duplicate a symbol from the first file in the second file
        analysed_files[1].symbol_defs.append('foo_1')

        analyser = Analyse(root_symbol=None)

        with pytest.warns(UserWarning):
            result = analyser._gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }

    def test_special_measures(self, analysed_files):
        analyser = Analyse(root_symbol=None)
        analyser.special_measure_analysis_results = analysed_files

        result = analyser._gen_symbol_table(analysed_files=[])

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }


class Test_add_unreferenced_deps(object):

    def test_vanilla(self):
        analyser = Analyse(root_symbol=None)

        # we analysed the source folder and found these symbols
        symbols = {
            "root": Path("root.f90"),
            "root_dep": Path("root_dep.f90"),
            "util": Path("util.f90"),
            "util_dep": Path("util_dep.f90"),
        }

        # we extracted the build tree
        build_tree = {
            Path('root.f90'): AnalysedFile(fpath=Path(), file_hash=None),
            Path('root_dep.f90'): AnalysedFile(fpath=Path(), file_hash=None),
        }

        # we want to force this symbol into the build [because it's not used via modules]
        analyser.unreferenced_deps = ['util']

        # the stuff to add to the build tree will be found in here
        all_analysed_files = {
            # root.f90 and root_util.f90 would also be in here but the test doesn't need them
            Path('util.f90'): AnalysedFile(fpath=Path('util.f90'), file_deps={Path('util_dep.f90')}, file_hash=None),
            Path('util_dep.f90'): AnalysedFile(fpath=Path('util_dep.f90'), file_hash=None),
        }

        analyser._add_unreferenced_deps(symbols=symbols, all_analysed_files=all_analysed_files, build_tree=build_tree)

        assert Path('util.f90') in build_tree
        assert Path('util_dep.f90') in build_tree

    # todo:
    # def test_duplicate(self):
    #     # ensure warning
    #     pass

from pathlib import Path
from unittest import mock

import pytest
from fab.util import HashedFile

from fab.build_config import BuildConfig
from fab.dep_tree import AnalysedFile, ParserWorkaround
from fab.steps.analyse import Analyse


@pytest.fixture
def analyser(tmp_path):
    analyser = Analyse()
    analyser._config = BuildConfig(
        'proj',
        fab_workspace=Path('tmp_path'),
        multiprocessing=False,
    )
    return analyser


class Test_gen_symbol_table(object):

    @pytest.fixture
    def analysed_files(self):
        return [AnalysedFile(fpath=Path('foo.c'), symbol_defs=['foo_1', 'foo_2'], file_hash=0),
                AnalysedFile(fpath=Path('bar.c'), symbol_defs=['bar_1', 'bar_2'], file_hash=0)]

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
        analysed_files[1].symbol_defs.add('foo_1')

        analyser = Analyse(root_symbol=None)

        with pytest.warns(UserWarning):
            result = analyser._gen_symbol_table(analysed_files=analysed_files)

        assert result == {
            'foo_1': Path('foo.c'),
            'foo_2': Path('foo.c'),
            'bar_1': Path('bar.c'),
            'bar_2': Path('bar.c'),
        }


class Test_gen_file_deps(object):

    def test_vanilla(self, analyser):

        my_file = Path('my_file.f90')
        symbols = {
            'my_mod': my_file,
            'my_func': my_file,
            'dep1_mod': Path('dep1_mod.f90'),
            'dep2': Path('dep2.c'),
        }

        analysed_files = [
            mock.Mock(
                spec=AnalysedFile, fpath=my_file, symbol_deps={'my_func', 'dep1_mod', 'dep2'}, file_deps=set()),
        ]

        analyser._gen_file_deps(analysed_files=analysed_files, symbols=symbols)

        assert analysed_files[0].file_deps == {symbols['dep1_mod'], symbols['dep2']}


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
            Path('root.f90'): AnalysedFile(fpath=Path(), file_hash=0),
            Path('root_dep.f90'): AnalysedFile(fpath=Path(), file_hash=0),
        }

        # we want to force this symbol into the build [because it's not used via modules]
        analyser.unreferenced_deps = ['util']

        # the stuff to add to the build tree will be found in here
        all_analysed_files = {
            # root.f90 and root_util.f90 would also be in here but the test doesn't need them
            Path('util.f90'): AnalysedFile(fpath=Path('util.f90'), file_deps={Path('util_dep.f90')}, file_hash=0),
            Path('util_dep.f90'): AnalysedFile(fpath=Path('util_dep.f90'), file_hash=0),
        }

        analyser._add_unreferenced_deps(symbols=symbols, all_analysed_files=all_analysed_files, build_tree=build_tree)

        assert Path('util.f90') in build_tree
        assert Path('util_dep.f90') in build_tree

    # todo:
    # def test_duplicate(self):
    #     # ensure warning
    #     pass


class Test_parse_files(object):

    def test_exceptions(self):
        # make sure parse exceptions do not stop the build
        with mock.patch('fab.steps.Step.run_mp', return_value=[Exception('foo')]):
            Analyse(root_symbol=None)._parse_files(files=[])


class Test_add_manual_results(object):

    def test_vanilla(self):
        # test normal usage of manual analysis results
        input = ParserWorkaround(fpath=Path('foo.f'), symbol_defs={'foo', })
        expect = AnalysedFile(fpath=Path('foo.f'), file_hash=123, symbol_defs={'foo', })

        analyser = Analyse(special_measure_analysis_results=[input])
        analysed_files = set()

        with mock.patch('fab.dep_tree.file_checksum', return_value=HashedFile(None, 123)):
            analyser._add_manual_results(analysed_files=analysed_files)

        assert analysed_files == {expect}

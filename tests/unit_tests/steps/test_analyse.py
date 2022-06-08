from pathlib import Path
from unittest import mock
from unittest.mock import mock_open

import pytest
from fab.util import HashedFile

from fab.dep_tree import AnalysedFile
from fab.steps.analyse import Analyse


# These methods are just glue code and do not currently have a test.
#   _analyse_source_code
#   _analyse_dependencies
#   _parse_files


@pytest.fixture
def analyser():
    analyser = Analyse()
    analyser._config = mock.Mock(multiprocessing=False, project_workspace=Path('workspace'))
    return analyser


def test_get_file_checksums(analyser):
    # ensure this function returns the expected data structure

    fpaths = [Path('foo.c'), Path('bar.c')]

    def fake_hasher(fpath):
        return HashedFile(fpath, hash(str(fpath)))

    # we don't actually try to hash the files in this test, we just return something repeatable as a fake hash
    with mock.patch('fab.steps.analyse.do_checksum', side_effect=fake_hasher):
        result = analyser._get_file_checksums(fpaths)

    expected = {fpath: hash(str(fpath)) for fpath in fpaths}
    assert result == expected


class Test_load_analysis_results(object):

    @pytest.fixture
    def csv_lines(self):
        # a module with a dependecy on a fortran and c file, plus a mo commented dep
        return [
            'fpath,file_hash,symbol_defs,symbol_deps,file_deps,mo_commented_file_deps',
            'my_mod.f90,123,my_mod,dep1_mod;dep2,,mo_dep.c',
            'dep1_mod.f90,234,dep1_mod,,,',
            'dep2.c,345,dep2,,,',
        ]

    @pytest.fixture
    def latest_file_hashes(self):
        return {Path('my_mod.f90'): 123, Path('dep1_mod.f90'): 234, Path('dep2.c'): 345}

    def test_no_analysis_file(self, analyser):
        # there's nothing to load
        with mock.patch('fab.steps.analyse.open', side_effect=FileNotFoundError('mwah-ha-ha-haa')):
            results = analyser._load_analysis_results(latest_file_hashes=dict())

        assert results == dict()

    def test_nothing_changed(self, analyser, csv_lines, latest_file_hashes):
        # a simple example of a fortran module depending on a fortran and a c file

        file_data = "\n".join(csv_lines)
        with mock.patch('fab.steps.analyse.open', mock_open(read_data=file_data)):
            results = analyser._load_analysis_results(latest_file_hashes=latest_file_hashes)

        expected = {
            Path('my_mod.f90'): AnalysedFile(
                fpath=Path('my_mod.f90'), file_hash=123, symbol_defs={'my_mod', }, symbol_deps={'dep1_mod', 'dep2'},
                mo_commented_file_deps={'mo_dep.c', }),
            Path('dep1_mod.f90'): AnalysedFile(
                fpath=Path('dep1_mod.f90'), file_hash=234, symbol_defs={'dep1_mod', }),
            Path('dep2.c'): AnalysedFile(
                fpath=Path('dep2.c'), file_hash=345, symbol_defs={'dep2', }),
        }

        assert results == expected

    def test_missing_file(self, analyser, csv_lines, latest_file_hashes):
        # a previously analysed file is no longer present

        # remove a file
        del latest_file_hashes[Path('dep2.c')]

        file_data = "\n".join(csv_lines)
        with mock.patch('fab.steps.analyse.open', mock_open(read_data=file_data)):
            results = analyser._load_analysis_results(latest_file_hashes=latest_file_hashes)

        expected = {
            Path('my_mod.f90'): AnalysedFile(
                fpath=Path('my_mod.f90'), file_hash=123, symbol_defs={'my_mod', }, symbol_deps={'dep1_mod', 'dep2'},
                mo_commented_file_deps={'mo_dep.c', }),
            Path('dep1_mod.f90'): AnalysedFile(
                fpath=Path('dep1_mod.f90'), file_hash=234, symbol_defs={'dep1_mod', }),
        }

        assert results == expected


class Test_what_needs_reanalysing(object):

    def test_vanilla(self, analyser):
        # ensure we know when a file has changed since we last analysed it

        prev_results = {
            Path('foo.f90'): mock.Mock(spec=AnalysedFile, file_hash=123),
            Path('bar.f90'): mock.Mock(spec=AnalysedFile, file_hash=456),
        }

        latest_file_hashes = {
            Path('foo.f90'): 999999,
            Path('bar.f90'): 456,
        }

        changed, unchanged = analyser._what_needs_reanalysing(
            prev_results=prev_results, latest_file_hashes=latest_file_hashes)

        assert changed == {HashedFile(Path('foo.f90'), 999999, )}
        assert unchanged == {prev_results[Path('bar.f90')], }


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


class Test_gen_file_deps(object):

    def test_vanilla(self, analyser):

        symbols = {
            'my_mod': Path('my_mod.f90'),
            'dep1_mod': Path('dep1_mod.f90'),
            'dep2': Path('dep2.c'),
        }

        analysed_files = [
            mock.Mock(spec=AnalysedFile, symbol_deps={'dep1_mod', 'dep2'}, file_deps=set()),
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
